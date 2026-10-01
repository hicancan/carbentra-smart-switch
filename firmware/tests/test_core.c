#include "switch_core.h"
#include "meter.h"
#include "command_json.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static const char *boot="0123456789abcdef0123456789abcdef";
static switch_command_t command(void){switch_command_t c={.seq=1,.expires_uptime_ms=5000,.channel=1,.on=true};strcpy(c.id,"request-1");strcpy(c.boot_id,boot);return c;}
static void control_tests(void){
    switch_state_t s;switch_init(&s,boot);switch_configure(&s,true,0,false,SWITCH_MANUAL_HOLD_MS);for(unsigned i=0;i<3;i++)assert(!s.commanded[i]);
    assert(!switch_key_sample(&s,0,true,200));assert(!s.commanded[0]);
    assert(!switch_key_sample(&s,0,false,201));assert(!switch_key_sample(&s,0,false,236));
    assert(!switch_key_sample(&s,0,true,240));assert(!switch_key_sample(&s,0,false,245));assert(!switch_key_sample(&s,0,true,250));
    assert(!switch_key_sample(&s,0,true,284));assert(switch_key_sample(&s,0,true,285));assert(s.commanded[0]);
    assert(!switch_key_sample(&s,0,true,999));assert(!switch_key_sample(&s,3,true,1000));
    s.hold_until_ms[0]=0;switch_command_t c=command();assert(switch_apply(&s,&c,1000)==SWITCH_APPLIED);
    s.commanded[0]=false;assert(switch_apply(&s,&c,8000)==SWITCH_DUPLICATE);assert(!s.commanded[0]);
    c.on=false;assert(switch_apply(&s,&c,1001)==SWITCH_ID_CONFLICT);
    c=command();strcpy(c.id,"next");assert(switch_apply(&s,&c,1001)==SWITCH_STALE_SEQUENCE);
    c.seq=2;c.expires_uptime_ms=1001;assert(switch_apply(&s,&c,1001)==SWITCH_EXPIRED);
    c.expires_uptime_ms=31002;assert(switch_apply(&s,&c,1001)==SWITCH_EXPIRED);
    c.expires_uptime_ms=31001;assert(switch_apply(&s,&c,1001)==SWITCH_APPLIED);
    c.seq=3;strcpy(c.id,"wrong-boot");c.boot_id[0]='a';assert(switch_apply(&s,&c,1001)==SWITCH_WRONG_BOOT);
    c=command();c.channel=4;assert(switch_apply(&s,&c,1001)==SWITCH_INVALID);
    c=command();c.seq=0;assert(switch_apply(&s,&c,1001)==SWITCH_INVALID);
    char invalid[49];memset(invalid,'x',sizeof(invalid));assert(!switch_valid_id(invalid,48));
    uint64_t n=0;assert(switch_parse_u64("18446744073709551615",&n)&&n==UINT64_MAX);assert(!switch_parse_u64("18446744073709551616",&n));assert(!switch_parse_u64("1e2",&n));assert(!switch_parse_u64("-1",&n));assert(!switch_parse_u64("",&n));
    switch_init(&s,boot);switch_configure(&s,true,0,false,SWITCH_MANUAL_HOLD_MS);c=command();
    for(unsigned i=1;i<=20;i++){snprintf(c.id,sizeof(c.id),"id-%u",i);c.seq=i;assert(switch_apply(&s,&c,1000)==SWITCH_APPLIED);}
    c.seq=1;strcpy(c.id,"id-1");assert(switch_apply(&s,&c,1000)==SWITCH_STALE_SEQUENCE);
}
static void press(switch_state_t *s,unsigned channel,uint64_t now){
    switch_key_sample(s,channel,false,now);switch_key_sample(s,channel,false,now+35);
    switch_key_sample(s,channel,true,now+40);assert(switch_key_sample(s,channel,true,now+75));
}
static void safety_and_hold_tests(void){
    switch_state_t s;switch_init(&s,boot);switch_command_t c=command();
    assert(switch_apply(&s,&c,1000)==SWITCH_NOT_COMMISSIONED);
    press(&s,0,1000);assert(!s.commanded[0]&&s.local_event_result==SWITCH_NOT_COMMISSIONED);
    assert(s.local_event_seq==1&&s.local_event_channel==1&&s.local_event_ms==1075);
    assert(switch_channel_mode(&s,0,1075)==SWITCH_MODE_MANUAL);
    switch_configure(&s,true,0,false,1000);s.hold_until_ms[0]=0;
    press(&s,0,2000);assert(s.commanded[0]);
    c.on=false;assert(switch_apply(&s,&c,2100)==SWITCH_MANUAL_HOLD);
    c.channel=2;assert(switch_apply(&s,&c,2100)==SWITCH_APPLIED);
    c.channel=1;c.seq=2;strcpy(c.id,"after-hold");
    assert(switch_apply(&s,&c,3074)==SWITCH_MANUAL_HOLD);
    assert(switch_apply(&s,&c,3075)==SWITCH_APPLIED&&!s.commanded[0]);
    switch_configure(&s,true,1,false,1000);c.seq=3;strcpy(c.id,"protected");
    assert(switch_apply(&s,&c,3076)==SWITCH_PROTECTED);
    press(&s,0,4000);assert(s.commanded[0]); /* real local input retained on protected circuit */
    switch_configure(&s,true,0,true,1000);assert(!s.commanded[0]);
    assert(switch_apply(&s,&c,4100)==SWITCH_MAINTENANCE);
    press(&s,0,4200);assert(!s.commanded[0]&&s.local_event_result==SWITCH_MAINTENANCE);
    switch_configure(&s,true,0,false,1000);switch_latch_fault(&s);
    assert(switch_apply(&s,&c,4400)==SWITCH_FAULT);
    press(&s,0,4500);assert(!s.commanded[0]&&s.local_event_result==SWITCH_FAULT);
    switch_init(&s,boot);switch_configure(&s,true,0,false,0);
    assert(s.manual_hold_ms==SWITCH_MANUAL_HOLD_MS);
    press(&s,0,UINT64_MAX-100);assert(s.hold_until_ms[0]==UINT64_MAX);
    assert(!strcmp(switch_mode_name(SWITCH_MODE_PROTECTED),"protected"));
}
static void protocol_tests(void){
    uint8_t request[8];const uint8_t expected[]={0xA5,8,0x41,0,2,0x4E,32,0x5E};
    assert(mcp_read_request(2,32,request)==8&&!memcmp(request,expected,8));assert(!mcp_read_request(2,33,request));
    uint8_t response[]={6,7,0x78,0x56,0x34,0x12,0x21},out[4];
    assert(mcp_read_response(response,sizeof(response),4,out));assert(meter_u32(out)==0x12345678);
    for(unsigned i=0;i<sizeof(response);i++){response[i]^=1;assert(!mcp_read_response(response,sizeof(response),4,out));response[i]^=1;}
    assert(!mcp_read_response(response,6,4,out));assert(!mcp_read_response(response,7,32,out));
    uint8_t m[28]={0x10,0,0,0,0x98,8},e[16]={0x01,0x02,0x03,0x04,0x05,0x06,0x07,0x08};
    meter_sample_t sample;assert(meter_decode(m,e,&sample));assert(sample.voltage_raw==2200&&sample.import_direction&&sample.import_raw==0x0807060504030201ULL);
    m[0]=0;meter_decode(m,e,&sample);assert(!sample.import_direction);
}
static void energy_tests(void){
    energy_state_t e;energy_init(&e,42);assert(e.gaps==1&&!e.known_mwh);
    assert(!energy_observe(&e,1000,1000,1));assert(energy_observe(&e,1500,2000,1));assert(e.known_mwh==500);
    assert(!energy_observe(&e,10,3000,1));assert(e.known_mwh==500&&e.gaps==2);
    assert(energy_observe(&e,20,4000,1)&&e.known_mwh==510);
    assert(!energy_observe(&e,UINT64_MAX,5000,1000));assert(e.known_mwh==510);
    energy_mark_gap(&e);assert(!e.baseline);assert(!energy_observe(&e,500,6000,1));assert(e.known_mwh==510);
    uint8_t checkpoint[32];energy_checkpoint(&e,checkpoint);energy_state_t restored;
    assert(energy_restore(&restored,checkpoint,32,42));assert(restored.known_mwh==510&&!restored.baseline&&restored.gaps==e.gaps+1);
    assert(!energy_restore(&restored,checkpoint,32,43));checkpoint[8]^=1;assert(!energy_restore(&restored,checkpoint,32,42));
    energy_init(&e,1);energy_observe(&e,0,1000,1);e.known_mwh=UINT64_MAX;assert(!energy_observe(&e,1,2000,1)&&e.overflow);
}
static void json_tests(void){
    switch_command_t c;const char *valid="{\"id\":\"cmd-1\",\"boot_id\":\"0123456789abcdef0123456789abcdef\",\"seq\":\"18446744073709551615\",\"channel\":2,\"on\":true,\"expires_uptime_ms\":\"4000\"}";
    assert(command_json_decode(valid,strlen(valid),&c)&&c.seq==UINT64_MAX&&c.channel==2&&c.on);
    const char *invalid[]={"{}","[]","{\"id\":\"x\",\"id\":\"y\"}","{\"seq\":9007199254740993}","{} garbage","{\"id\":\"x\\u0000y\"}"};
    for(unsigned i=0;i<sizeof(invalid)/sizeof(invalid[0]);i++)assert(!command_json_decode(invalid[i],strlen(invalid[i]),&c));
    char b[1024];strcpy(b,valid);char *p=strstr(b,"\"channel\":2");p[10]='4';assert(!command_json_decode(b,strlen(b),&c));
    strcpy(b,valid);b[strlen(b)-1]=0;strcat(b,",\"extra\":1}");assert(!command_json_decode(b,strlen(b),&c));
}
static void malformed_inputs(void){
    uint32_t rng=7;uint8_t bytes[768],out[32];switch_command_t cmd;
    for(unsigned run=0;run<2000;run++){size_t len=run%sizeof(bytes);for(size_t i=0;i<len;i++){rng=rng*1664525u+1013904223u;bytes[i]=(uint8_t)(rng>>24);}command_json_decode((const char*)bytes,len,&cmd);mcp_read_response(bytes,len,(uint8_t)(run%34),out);}
}
int main(void){malformed_inputs();control_tests();safety_and_hold_tests();protocol_tests();energy_tests();json_tests();puts("PASS: commissioning/actuation guards, channel-local manual hold, maintenance/protected/fault, debounced offline keys, replay/idempotency, meter frames, energy persistence and strict JSON groups");return 0;}
