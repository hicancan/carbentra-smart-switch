#include "command_json.h"
#include <math.h>
#include <string.h>
#include "cJSON.h"
bool command_json_decode(const char *data,size_t n,switch_command_t *out){
    if(!data || !out || n==0 || n>768 || memchr(data,0,n))return false;
    char bounded[769];memcpy(bounded,data,n);bounded[n]=0;
    if(strstr(bounded,"\\u0000"))return false;
    const char *end=NULL;cJSON *j=cJSON_ParseWithLengthOpts(bounded,n+1,&end,true);
    if(!j||!cJSON_IsObject(j)){cJSON_Delete(j);return false;}
    const char *names[]={"id","boot_id","seq","channel","on","expires_uptime_ms"};
    unsigned seen=0;bool valid=true;
    for(cJSON *item=j->child;item;item=item->next){unsigned k=0;for(;k<6;k++)if(item->string&&!strcmp(item->string,names[k]))break;
        if(k==6||(seen&(1u<<k))){valid=false;break;}seen|=1u<<k;}
    cJSON *id=cJSON_GetObjectItemCaseSensitive(j,"id"),*boot=cJSON_GetObjectItemCaseSensitive(j,"boot_id"),*seq=cJSON_GetObjectItemCaseSensitive(j,"seq"),*channel=cJSON_GetObjectItemCaseSensitive(j,"channel"),*on=cJSON_GetObjectItemCaseSensitive(j,"on"),*expiry=cJSON_GetObjectItemCaseSensitive(j,"expires_uptime_ms");
    valid=valid&&seen==63&&cJSON_IsString(id)&&switch_valid_id(id->valuestring,SWITCH_ID_MAX)&&cJSON_IsString(boot)&&strlen(boot->valuestring)==SWITCH_BOOT_ID_LEN&&cJSON_IsString(seq)&&cJSON_IsNumber(channel)&&isfinite(channel->valuedouble)&&channel->valuedouble>=1&&channel->valuedouble<=3&&floor(channel->valuedouble)==channel->valuedouble&&cJSON_IsBool(on)&&cJSON_IsString(expiry);
    memset(out,0,sizeof(*out));
    if(valid)valid=switch_parse_u64(seq->valuestring,&out->seq)&&switch_parse_u64(expiry->valuestring,&out->expires_uptime_ms);
    if(valid){strcpy(out->id,id->valuestring);strcpy(out->boot_id,boot->valuestring);out->channel=(uint8_t)channel->valueint;out->on=cJSON_IsTrue(on);}
    cJSON_Delete(j);return valid;
}
