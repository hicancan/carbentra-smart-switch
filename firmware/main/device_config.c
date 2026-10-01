#include "device_config.h"
#include "switch_core.h"
#include <stdlib.h>
#include <string.h>
#include "nvs.h"
#include "nvs_flash.h"
#include "esp_log.h"
static const char *TAG="factory";
static bool blob(nvs_handle_t h,const char *key,void *out,size_t expected) {
    size_t n=expected; return nvs_get_blob(h,key,out,&n)==ESP_OK && n==expected;
}
static bool str(nvs_handle_t h,const char *key,char *out,size_t cap) {
    size_t n=cap; return nvs_get_str(h,key,out,&n)==ESP_OK && n>1 && n<=cap;
}
static char *text(nvs_handle_t h,const char *key,size_t max) {
    size_t n=0;
    if(nvs_get_str(h,key,NULL,&n)!=ESP_OK || n<2 || n>max) return NULL;
    char *p=calloc(n,1);
    if(p && nvs_get_str(h,key,p,&n)!=ESP_OK) {free(p);return NULL;}
    return p;
}
static bool uri_valid(const char *p) {
    if(!p || strncmp(p,"mqtts://",8))return false;
    p+=8; size_t host=0;
    while(*p && *p!=':') {char c=*p++;if(!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='.'||c=='-'))return false;host++;}
    if(!host || host>253)return false;
    if(*p==':') {uint64_t port=0;if(!switch_parse_u64(p+1,&port)||port<1||port>65535)return false;}
    return true;
}
void device_config_load(device_config_t *c) {
    memset(c,0,sizeof(*c));
    c->manual_hold_ms=SWITCH_MANUAL_HOLD_MS;
    if(nvs_flash_init_partition("factory")!=ESP_OK) {ESP_LOGW(TAG,"Factory partition unavailable; local keys only");return;}
    nvs_handle_t h;
    if(nvs_open_from_partition("factory","switchcfg",NVS_READONLY,&h)!=ESP_OK)return;
    uint8_t commissioned=0, maintenance=0;
    nvs_get_u8(h,"commissioned",&commissioned);
    esp_err_t maintenance_status=nvs_get_u8(h,"maintenance",&maintenance);
    esp_err_t protected_status=nvs_get_u8(h,"protected_mask",&c->protected_mask);
    if(maintenance_status!=ESP_OK&&maintenance_status!=ESP_ERR_NVS_NOT_FOUND)maintenance=1;
    if(protected_status!=ESP_OK&&protected_status!=ESP_ERR_NVS_NOT_FOUND)c->protected_mask=7;
    nvs_get_u32(h,"manual_hold_ms",&c->manual_hold_ms);
    c->commissioned=commissioned==1;
    c->maintenance=maintenance!=0;
    if(c->protected_mask>7)c->protected_mask=7;
    if(!c->manual_hold_ms||c->manual_hold_ms>SWITCH_MAX_MANUAL_HOLD_MS)c->manual_hold_ms=SWITCH_MANUAL_HOLD_MS;
    bool identity=str(h,"device_id",c->device_id,sizeof(c->device_id))&&switch_valid_id(c->device_id,32);
    c->provisioning_ready=identity&&blob(h,"prov_salt",c->salt,sizeof(c->salt))&&blob(h,"prov_verifier",c->verifier,sizeof(c->verifier));
    c->broker_uri=text(h,"mqtt_uri",320); c->ca_pem=text(h,"ca_pem",8192);
    c->client_cert=text(h,"client_cert",8192); c->client_key=text(h,"client_key",8192);
    c->mqtt_ready=identity&&uri_valid(c->broker_uri)&&c->ca_pem&&c->client_cert&&c->client_key&&
        strstr(c->ca_pem,"-----BEGIN CERTIFICATE-----")&&strstr(c->client_cert,"-----BEGIN CERTIFICATE-----")&&
        (strstr(c->client_key,"-----BEGIN PRIVATE KEY-----")||strstr(c->client_key,"-----BEGIN RSA PRIVATE KEY-----")||strstr(c->client_key,"-----BEGIN EC PRIVATE KEY-----"));
    c->calibration_ready=blob(h,"meter_profile",c->meter_profile,sizeof(c->meter_profile))&&
        str(h,"cal_id",c->calibration_id,sizeof(c->calibration_id))&&switch_valid_id(c->calibration_id,48)&&
        nvs_get_u32(h,"voltage_uv",&c->voltage_uv)==ESP_OK&&c->voltage_uv>0&&c->voltage_uv<=1000000&&
        nvs_get_u32(h,"current_ua",&c->current_ua)==ESP_OK&&c->current_ua>0&&c->current_ua<=1000000&&
        nvs_get_u32(h,"power_mw",&c->power_mw)==ESP_OK&&c->power_mw>0&&c->power_mw<=1000000&&
        nvs_get_u32(h,"energy_mwh",&c->energy_mwh)==ESP_OK&&c->energy_mwh>0&&c->energy_mwh<=1000000;
    /* Profile must have accumulation ON, ADCs running, 9600 baud, two-wire UART. */
    uint32_t sys=meter_u32(c->meter_profile+0x94-MCP_PROFILE_START);
    if((sys&1)==0 || (sys&0x178)!=0 || (sys&0xE000)!=0x8000)c->calibration_ready=false;
    uint32_t crc=meter_crc32(c->meter_profile,sizeof(c->meter_profile));
    uint8_t scales[16]; uint32_t values[]={c->voltage_uv,c->current_ua,c->power_mw,c->energy_mwh};
    for(unsigned i=0;i<4;i++)for(unsigned j=0;j<4;j++)scales[i*4+j]=(uint8_t)(values[i]>>(j*8));
    c->profile_crc=crc^meter_crc32(scales,sizeof(scales))^meter_crc32((const uint8_t*)c->calibration_id,strlen(c->calibration_id));
    nvs_close(h);
    ESP_LOGI(TAG,"Provisioning %s, MQTT %s, calibration %s",c->provisioning_ready?"configured":"missing",c->mqtt_ready?"configured":"missing",c->calibration_ready?"pending meter readback":"missing");
}
