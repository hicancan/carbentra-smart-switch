#include "network.h"
#include "app_state.h"
#include "command_json.h"
#include <inttypes.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "freertos/task.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_sntp.h"
#include "esp_wifi.h"
#include "mqtt_client.h"
#include "wifi_provisioning/manager.h"
#include "wifi_provisioning/scheme_ble.h"
#include "cJSON.h"
#define WIFI_UP BIT0
#define MQTT_UP BIT1
#define MAX_COMMAND_BYTES 768
static const char *TAG="network";
static EventGroupHandle_t events;
static const device_config_t *cfg;
static esp_mqtt_client_handle_t mqtt;
static char command_topic[96],state_topic[96],ack_topic[96],availability_topic[96];
static char incoming[MAX_COMMAND_BYTES+1];
static size_t incoming_length, incoming_expected;
static bool incoming_allowed;
static wifi_prov_security2_params_t security;
static uint64_t sample_seq;
static portMUX_TYPE sample_seq_lock=portMUX_INITIALIZER_UNLOCKED;
static uint64_t next_sample_seq(void){
    portENTER_CRITICAL(&sample_seq_lock);
    uint64_t next=sample_seq==UINT64_MAX?0:++sample_seq;
    portEXIT_CRITICAL(&sample_seq_lock);return next;
}
static void add_u64(cJSON *o,const char *name,uint64_t v){char b[24];snprintf(b,sizeof(b),"%" PRIu64,v);cJSON_AddStringToObject(o,name,b);}
static void send_json(const char *topic,cJSON *json,int qos,int retain){
    if(!json)return;
    char *text=cJSON_PrintUnformatted(json);
    if(text){if(mqtt&&(xEventGroupGetBits(events)&MQTT_UP))esp_mqtt_client_enqueue(mqtt,topic,text,0,qos,retain,false);free(text);}
    cJSON_Delete(json);
}
static void publish_state(void){
    app_snapshot_t s;app_snapshot(&s);
    cJSON *j=cJSON_CreateObject();if(!j)return;
    cJSON_AddNumberToObject(j,"schema_version",1);
    cJSON_AddStringToObject(j,"device_type","smart_switch");
    cJSON_AddStringToObject(j,"device_id",cfg->device_id);cJSON_AddStringToObject(j,"boot_id",s.control.boot_id);
    uint64_t sequence=next_sample_seq();if(!sequence){cJSON_Delete(j);return;}
    add_u64(j,"sample_seq",sequence);
    add_u64(j,"uptime_ms",s.uptime_ms);add_u64(j,"last_seq",s.control.last_seq);
    cJSON_AddBoolToObject(j,"actuation_enabled",s.control.commissioned);
    cJSON_AddBoolToObject(j,"fault_latched",s.control.fault_latched);
    cJSON_AddBoolToObject(j,"maintenance",s.control.maintenance);
    cJSON_AddNumberToObject(j,"protected_channel_mask",s.control.protected_mask);
    cJSON *local=cJSON_AddObjectToObject(j,"last_local_input");
    cJSON_AddNumberToObject(local,"channel",s.control.local_event_channel);
    add_u64(local,"event_seq",s.control.local_event_seq);
    add_u64(local,"uptime_ms",s.control.local_event_ms);
    cJSON_AddBoolToObject(local,"pressed",s.control.local_event_seq!=0);
    cJSON_AddStringToObject(local,"result",s.control.local_event_seq?switch_result_name(s.control.local_event_result):"none");
    cJSON_AddStringToObject(j,"source_mode","REAL");
    cJSON *channels=cJSON_AddArrayToObject(j,"channels");
    for(unsigned i=0;i<3;i++){
        cJSON *ch=cJSON_CreateObject();char channel_id[16];snprintf(channel_id,sizeof(channel_id),"lighting-%u",i+1);
        cJSON_AddStringToObject(ch,"channel_id",channel_id);cJSON_AddNumberToObject(ch,"channel",i+1);
        cJSON_AddBoolToObject(ch,"commanded_on",s.control.commanded[i]);cJSON_AddNullToObject(ch,"physically_verified_on");
        cJSON_AddStringToObject(ch,"feedback_quality","unavailable_no_independent_sensor");
        cJSON_AddStringToObject(ch,"control_mode",switch_mode_name(switch_channel_mode(&s.control,i,s.uptime_ms)));
        add_u64(ch,"manual_hold_until_uptime_ms",s.control.hold_until_ms[i]);
        cJSON_AddItemToArray(channels,ch);
    }
    cJSON *meter=cJSON_AddObjectToObject(j,"aggregate_meter");
    bool fresh=s.meter_online&&s.uptime_ms>=s.meter_observed_ms&&s.uptime_ms-s.meter_observed_ms<=5000;
    cJSON_AddStringToObject(meter,"scope","three_lighting_outputs_total");
    cJSON_AddStringToObject(meter,"quality",!fresh?"unavailable":!s.calibrated?"uncalibrated":"calibrated_readback");
    cJSON_AddStringToObject(meter,"calibration_id",cfg->calibration_id);
    if(fresh){add_u64(meter,"observed_uptime_ms",s.meter_observed_ms);cJSON_AddNumberToObject(meter,"status_bits",s.meter.status);}
    if(fresh&&s.calibrated){
        cJSON_AddNumberToObject(meter,"voltage_v",(double)s.meter.voltage_raw*cfg->voltage_uv/1000000.0);
        cJSON_AddNumberToObject(meter,"current_a",(double)s.meter.current_raw*cfg->current_ua/1000000.0);
        cJSON_AddNumberToObject(meter,"active_power_w",(s.meter.import_direction?1.0:-1.0)*s.meter.power_raw*cfg->power_mw/1000.0);
        add_u64(meter,"raw_import_counter",s.meter.import_raw);add_u64(meter,"raw_export_counter",s.meter.export_raw);
    }else{cJSON_AddNullToObject(meter,"voltage_v");cJSON_AddNullToObject(meter,"current_a");cJSON_AddNullToObject(meter,"active_power_w");}
    if(s.calibrated&&s.energy_storage_ok&&!s.energy.overflow){
        char wh[32];snprintf(wh,sizeof(wh),"%" PRIu64 ".%03u",s.energy.known_mwh/1000,(unsigned)(s.energy.known_mwh%1000));
        cJSON_AddStringToObject(meter,"known_energy_wh",wh);
    }else cJSON_AddNullToObject(meter,"known_energy_wh");
    cJSON_AddStringToObject(meter,"energy_quality","partial_lower_bound");
    cJSON_AddBoolToObject(meter,"persistent_storage_ok",s.energy_storage_ok);
    cJSON_AddNumberToObject(meter,"unknown_intervals",s.energy.gaps);
    cJSON_AddNumberToObject(meter,"checkpoint_interval_seconds",60);
    send_json(state_topic,j,0,1);
}
static void acknowledge(const switch_command_t *cmd,const char *result){
    app_snapshot_t s;app_snapshot(&s);cJSON *j=cJSON_CreateObject();if(!j)return;
    cJSON_AddStringToObject(j,"device_id",cfg->device_id);cJSON_AddStringToObject(j,"boot_id",s.control.boot_id);
    if(cmd){cJSON_AddStringToObject(j,"id",cmd->id);add_u64(j,"seq",cmd->seq);cJSON_AddNumberToObject(j,"channel",cmd->channel);}
    cJSON_AddStringToObject(j,"result",result);cJSON_AddBoolToObject(j,"physical_verification",false);
    add_u64(j,"uptime_ms",s.uptime_ms);send_json(ack_topic,j,1,0);
}
static void mqtt_event(void *arg,esp_event_base_t base,int32_t id,void *event_data){
    (void)arg;(void)base;esp_mqtt_event_handle_t e=event_data;
    switch(id){
    case MQTT_EVENT_CONNECTED:
        xEventGroupSetBits(events,MQTT_UP);esp_mqtt_client_subscribe(mqtt,command_topic,1);
        esp_mqtt_client_enqueue(mqtt,availability_topic,"online",0,1,1,false);publish_state();break;
    case MQTT_EVENT_DISCONNECTED:xEventGroupClearBits(events,MQTT_UP);incoming_allowed=false;break;
    case MQTT_EVENT_DATA:
        if(e->current_data_offset==0){
            incoming_length=0;incoming_expected=(size_t)e->total_data_len;
            incoming_allowed=e->total_data_len>0&&e->total_data_len<=MAX_COMMAND_BYTES&&!e->retain&&e->topic_len==(int)strlen(command_topic)&&!memcmp(e->topic,command_topic,e->topic_len);
        }
        if(!incoming_allowed)break;
        if(e->current_data_offset<0||(size_t)e->current_data_offset!=incoming_length||e->data_len<0||incoming_length+(size_t)e->data_len>incoming_expected){incoming_allowed=false;break;}
        memcpy(incoming+incoming_length,e->data,e->data_len);incoming_length+=(size_t)e->data_len;
        if(incoming_length==incoming_expected){
            incoming[incoming_length]=0;incoming_allowed=false;
            switch_command_t command;
            if(memchr(incoming,0,incoming_length)||!command_json_decode(incoming,incoming_length,&command)){acknowledge(NULL,"invalid_command");break;}
            switch_result_t result=app_command(&command);acknowledge(&command,switch_result_name(result));publish_state();
        }break;
    default:break;
    }
}
static void wifi_event(void *arg,esp_event_base_t base,int32_t id,void *data){
    (void)arg;(void)data;
    if(base==WIFI_PROV_EVENT){
        if(id==WIFI_PROV_END)wifi_prov_mgr_deinit();
        else if(id==WIFI_PROV_CRED_FAIL){ESP_LOGW(TAG,"Provisioning Wi-Fi connection failed");wifi_prov_mgr_reset_sm_state_on_failure();}
        /* Never log credentials or received provisioning payloads. */
    }else if(base==WIFI_EVENT&&id==WIFI_EVENT_STA_START)esp_wifi_connect();
    else if(base==WIFI_EVENT&&id==WIFI_EVENT_STA_DISCONNECTED){xEventGroupClearBits(events,WIFI_UP);esp_wifi_connect();}
    else if(base==IP_EVENT&&id==IP_EVENT_STA_GOT_IP)xEventGroupSetBits(events,WIFI_UP);
}
static void network_task(void *unused){
    (void)unused;xEventGroupWaitBits(events,WIFI_UP,false,true,portMAX_DELAY);
    esp_sntp_setoperatingmode(SNTP_OPMODE_POLL);esp_sntp_setservername(0,"pool.ntp.org");esp_sntp_init();
    /* Certificate validity checks need usable wall time; commands themselves use boot-relative TTL. */
    while(time(NULL)<1735689600)vTaskDelay(pdMS_TO_TICKS(1000));
    if(!cfg->mqtt_ready){ESP_LOGW(TAG,"Authenticated broker configuration missing; local switching remains active");vTaskDelete(NULL);return;}
    snprintf(command_topic,sizeof(command_topic),"carbentra/switch/%s/command",cfg->device_id);
    snprintf(state_topic,sizeof(state_topic),"carbentra/switch/%s/state",cfg->device_id);
    snprintf(ack_topic,sizeof(ack_topic),"carbentra/switch/%s/ack",cfg->device_id);
    snprintf(availability_topic,sizeof(availability_topic),"carbentra/switch/%s/availability",cfg->device_id);
    esp_mqtt_client_config_t mc={
        .broker.address.uri=cfg->broker_uri,
        .broker.verification.certificate=cfg->ca_pem,
        .broker.verification.skip_cert_common_name_check=false,
        .credentials.client_id=cfg->device_id,
        .credentials.authentication.certificate=cfg->client_cert,
        .credentials.authentication.key=cfg->client_key,
        .session.keepalive=30,
        .session.last_will.topic=availability_topic,.session.last_will.msg="offline",.session.last_will.qos=1,.session.last_will.retain=1,
        .network.disable_auto_reconnect=false,.network.reconnect_timeout_ms=5000,
        .buffer.size=1024,.buffer.out_size=2048,
    };
    mqtt=esp_mqtt_client_init(&mc);
    if(!mqtt||esp_mqtt_client_register_event(mqtt,ESP_EVENT_ANY_ID,mqtt_event,NULL)!=ESP_OK||esp_mqtt_client_start(mqtt)!=ESP_OK){ESP_LOGE(TAG,"MQTT startup failed; local switching remains active");vTaskDelete(NULL);return;}
    for(;;){if(xEventGroupGetBits(events)&MQTT_UP)publish_state();vTaskDelay(pdMS_TO_TICKS(2000));}
}
void network_start(const device_config_t *config){
    cfg=config;events=xEventGroupCreate();if(!events)return;
    if(esp_netif_init()!=ESP_OK||esp_event_loop_create_default()!=ESP_OK)return;
    if(!esp_netif_create_default_wifi_sta())return;
    wifi_init_config_t wi=WIFI_INIT_CONFIG_DEFAULT();if(esp_wifi_init(&wi)!=ESP_OK)return;
    esp_event_handler_register(WIFI_EVENT,ESP_EVENT_ANY_ID,wifi_event,NULL);
    esp_event_handler_register(IP_EVENT,IP_EVENT_STA_GOT_IP,wifi_event,NULL);
    esp_event_handler_register(WIFI_PROV_EVENT,ESP_EVENT_ANY_ID,wifi_event,NULL);
    wifi_prov_mgr_config_t prov={.scheme=wifi_prov_scheme_ble,.scheme_event_handler=WIFI_PROV_SCHEME_BLE_EVENT_HANDLER_FREE_BTDM};
    if(wifi_prov_mgr_init(prov)!=ESP_OK)return;
    bool provisioned=false;if(wifi_prov_mgr_is_provisioned(&provisioned)!=ESP_OK)return;
    if(!provisioned){
        if(!cfg->provisioning_ready){ESP_LOGW(TAG,"Unique SRP salt/verifier absent; BLE provisioning stays disabled");wifi_prov_mgr_deinit();return;}
        security=(wifi_prov_security2_params_t){.salt=(const char *)cfg->salt,.salt_len=sizeof(cfg->salt),.verifier=(const char *)cfg->verifier,.verifier_len=sizeof(cfg->verifier)};
        uint8_t mac[6];esp_wifi_get_mac(WIFI_IF_STA,mac);
        char service[20];snprintf(service,sizeof(service),"CSW_%02X%02X%02X%02X%02X%02X",mac[0],mac[1],mac[2],mac[3],mac[4],mac[5]);
        if(wifi_prov_mgr_start_provisioning(WIFI_PROV_SECURITY_2,&security,service,NULL)!=ESP_OK)return;
        ESP_LOGI(TAG,"BLE secure provisioning active");
    }else{wifi_prov_mgr_deinit();esp_wifi_set_mode(WIFI_MODE_STA);esp_wifi_start();}
    xTaskCreate(network_task,"secure_mqtt",6144,NULL,4,NULL);
}
