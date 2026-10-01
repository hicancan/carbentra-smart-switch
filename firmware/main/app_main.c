#include <inttypes.h>
#include <stdio.h>
#include "bootloader_random.h"
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "driver/gpio.h"
#include "driver/uart.h"
#include "esp_log.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "nvs_flash.h"
#include "nvs.h"
#include "board.h"
#include "app_state.h"
#include "device_config.h"
#include "network.h"
static const char *TAG="switch";
static const int relays[]={RELAY1_GPIO,RELAY2_GPIO,RELAY3_GPIO};
static const int keys[]={KEY1_GPIO,KEY2_GPIO,KEY3_GPIO};
static app_snapshot_t state;
static SemaphoreHandle_t state_lock;
static device_config_t config;
static uint64_t now_ms(void){return (uint64_t)esp_timer_get_time()/1000;}
static void drive_outputs(void){
    for(unsigned i=0;i<3;i++){
#if CONFIG_CARBENTRA_SWITCH_ALLOW_ACTUATION
        bool on=state.control.commissioned&&!state.control.fault_latched&&!state.control.maintenance&&state.control.commanded[i];
#else
        bool on=false;
#endif
        if(gpio_set_level(relays[i],on?1:0)!=ESP_OK){
            switch_latch_fault(&state.control);
            for(unsigned j=0;j<3;j++)gpio_set_level(relays[j],0);
            break;
        }
    }
}
void app_snapshot(app_snapshot_t *out){xSemaphoreTake(state_lock,portMAX_DELAY);*out=state;out->uptime_ms=now_ms();xSemaphoreGive(state_lock);}
switch_result_t app_command(const switch_command_t *command){
    xSemaphoreTake(state_lock,portMAX_DELAY);
    switch_result_t result=switch_apply(&state.control,command,now_ms());
    if(result==SWITCH_APPLIED){drive_outputs();if(state.control.fault_latched)result=SWITCH_FAULT;}
    xSemaphoreGive(state_lock);return result;
}
static void key_task(void *unused){
    (void)unused;
    for(;;){
        xSemaphoreTake(state_lock,portMAX_DELAY);
        bool changed=false;uint64_t now=now_ms();
        for(unsigned i=0;i<3;i++)changed|=switch_key_sample(&state.control,i,gpio_get_level(keys[i])==0,now);
        if(changed)drive_outputs();
        xSemaphoreGive(state_lock);vTaskDelay(pdMS_TO_TICKS(10));
    }
}
static bool read_registers(uint16_t address,uint8_t *data,uint8_t count){
    uint8_t request[8],frame[35];size_t have=0,total=(size_t)count+3;
    if(!mcp_read_request(address,count,request))return false;
    uart_flush_input(METER_UART);
    if(uart_write_bytes(METER_UART,request,sizeof(request))!=(int)sizeof(request))return false;
    uint64_t deadline=now_ms()+250;
    while(have<total && now_ms()<deadline){
        int n=uart_read_bytes(METER_UART,frame+have,total-have,pdMS_TO_TICKS(20));
        if(n>0)have+=(size_t)n;
        if(have && frame[0]!=0x06)return false;
    }
    return mcp_read_response(frame,have,count,data);
}
static bool profile_matches(void){
    if(!config.calibration_ready)return false;
    /* Unframed 0x5A is the documented model probe, not the framed calibration command. */
    const uint8_t probe=0x5A;uint8_t identity[2];uart_flush_input(METER_UART);
    if(uart_write_bytes(METER_UART,&probe,1)!=1 || uart_read_bytes(METER_UART,identity,2,pdMS_TO_TICKS(200))!=2 || identity[0]!=0x15 || identity[1]!=0x04)return false;
    uint8_t bytes[32];
    for(size_t offset=0;offset<MCP_PROFILE_SIZE;offset+=32){
        size_t n=MCP_PROFILE_SIZE-offset;if(n>32)n=32;
        if(!read_registers(MCP_PROFILE_START+offset,bytes,(uint8_t)n)||memcmp(bytes,config.meter_profile+offset,n))return false;
    }
    return true;
}
static void meter_task(void *unused){
    (void)unused;
    uart_config_t uart={.baud_rate=METER_BAUD,.data_bits=UART_DATA_8_BITS,.parity=UART_PARITY_DISABLE,.stop_bits=UART_STOP_BITS_1,.flow_ctrl=UART_HW_FLOWCTRL_DISABLE,.source_clk=UART_SCLK_DEFAULT};
    if(uart_param_config(METER_UART,&uart)!=ESP_OK||uart_set_pin(METER_UART,METER_TX_GPIO,METER_RX_GPIO,UART_PIN_NO_CHANGE,UART_PIN_NO_CHANGE)!=ESP_OK||uart_driver_install(METER_UART,256,0,0,NULL,0)!=ESP_OK){ESP_LOGE(TAG,"Meter UART unavailable");vTaskDelete(NULL);return;}
    nvs_handle_t store=0;bool storage=config.calibration_ready&&nvs_flash_init_partition("energy")==ESP_OK&&nvs_open_from_partition("energy","energy",NVS_READWRITE,&store)==ESP_OK;
    energy_state_t energy;energy_init(&energy,config.profile_crc);
    if(storage){uint8_t data[ENERGY_CHECKPOINT_SIZE];size_t n=sizeof(data);esp_err_t e=nvs_get_blob(store,"checkpoint",data,&n);
        if(e!=ESP_ERR_NVS_NOT_FOUND && (e!=ESP_OK||!energy_restore(&energy,data,n,config.profile_crc)))storage=false;}
    uint64_t checked_at=0,saved_at=0;bool calibrated=false;
    for(;;){
        uint64_t now=now_ms();
        if(!checked_at||now-checked_at>=60000){calibrated=profile_matches();checked_at=now;}
        uint8_t measurements[28],counters[16];meter_sample_t sample={0};
        bool online=read_registers(0x0002,measurements,sizeof(measurements))&&read_registers(0x001E,counters,sizeof(counters))&&meter_decode(measurements,counters,&sample);
        /* AC-only calibrated design. DC mode cannot silently use AC calibration. */
        bool valid=online&&calibrated&&!(sample.status&0x8000);
        if(valid&&storage)energy_observe(&energy,sample.import_raw,now,config.energy_mwh);
        else energy_mark_gap(&energy);
        if(storage&&now-saved_at>=60000){uint8_t data[ENERGY_CHECKPOINT_SIZE];energy_checkpoint(&energy,data);
            if(nvs_set_blob(store,"checkpoint",data,sizeof(data))!=ESP_OK||nvs_commit(store)!=ESP_OK)storage=false;
            saved_at=now;}
        xSemaphoreTake(state_lock,portMAX_DELAY);
        state.meter_online=online;state.calibrated=valid;state.energy_storage_ok=storage;state.energy=energy;
        if(online){state.meter=sample;state.meter_observed_ms=now;}
        xSemaphoreGive(state_lock);
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}
void app_main(void){
    /* Output latch LOW before enabling drivers; external pulldowns cover reset/boot ROM. */
    for(unsigned i=0;i<3;i++){gpio_set_level(relays[i],0);gpio_set_direction(relays[i],GPIO_MODE_OUTPUT);gpio_set_level(relays[i],0);}
    for(unsigned i=0;i<3;i++){gpio_set_direction(keys[i],GPIO_MODE_INPUT);gpio_set_pull_mode(keys[i],GPIO_PULLUP_ONLY);}
    state_lock=xSemaphoreCreateMutex();if(!state_lock){ESP_LOGE(TAG,"No control mutex; outputs remain OFF");return;}
    uint8_t random[16];char boot[33];bootloader_random_enable();esp_fill_random(random,sizeof(random));bootloader_random_disable();
    for(unsigned i=0;i<16;i++)snprintf(boot+i*2,3,"%02x",random[i]);
    switch_init(&state.control,boot);
    device_config_load(&config);
#if CONFIG_CARBENTRA_SWITCH_ALLOW_ACTUATION
    bool commissioned=config.commissioned;
#else
    bool commissioned=false;
#endif
    switch_configure(&state.control,commissioned,config.protected_mask,config.maintenance,config.manual_hold_ms);
    xTaskCreate(key_task,"local_keys",2048,NULL,8,NULL);
    xTaskCreate(meter_task,"aggregate_meter",4096,NULL,5,NULL);
    if(nvs_flash_init()!=ESP_OK){ESP_LOGE(TAG,"Wi-Fi NVS unavailable; preserved storage, local control active");return;}
    network_start(&config);
}
