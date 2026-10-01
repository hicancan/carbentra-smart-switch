#include "meter.h"
#include <string.h>
static uint8_t sum8(const uint8_t *p, size_t n) { uint8_t s = 0; while (n--) s += *p++; return s; }
uint16_t meter_u16(const uint8_t *p) { return (uint16_t)p[0] | (uint16_t)p[1] << 8; }
uint32_t meter_u32(const uint8_t *p) { return (uint32_t)meter_u16(p) | (uint32_t)meter_u16(p+2) << 16; }
uint64_t meter_u64(const uint8_t *p) { return (uint64_t)meter_u32(p) | (uint64_t)meter_u32(p+4) << 32; }
static void put32(uint8_t *p, uint32_t n) { for (unsigned i=0;i<4;i++) p[i]=(uint8_t)(n>>(8*i)); }
static void put64(uint8_t *p, uint64_t n) { for (unsigned i=0;i<8;i++) p[i]=(uint8_t)(n>>(8*i)); }
uint32_t meter_crc32(const uint8_t *p, size_t n) {
    uint32_t crc = UINT32_MAX;
    while (n--) { crc ^= *p++; for (unsigned i=0;i<8;i++) crc=(crc>>1)^((crc&1)?0xEDB88320u:0); }
    return ~crc;
}
size_t mcp_read_request(uint16_t address, uint8_t count, uint8_t output[8]) {
    if (!output || !count || count > MCP_MAX_DATA) return 0;
    const uint8_t request[8] = {0xA5,8,0x41,(uint8_t)(address>>8),(uint8_t)address,0x4E,count,0};
    memcpy(output, request, 8); output[7]=sum8(output,7); return 8;
}
bool mcp_read_response(const uint8_t *frame, size_t length, uint8_t count, uint8_t *data) {
    if (!frame || !data || !count || count>MCP_MAX_DATA || length != (size_t)count+3 ||
        frame[0]!=0x06 || frame[1]!=length || sum8(frame,length-1)!=frame[length-1]) return false;
    memcpy(data,frame+2,count); return true;
}
bool meter_decode(const uint8_t m[28], const uint8_t e[16], meter_sample_t *out) {
    if (!m || !e || !out) return false;
    *out=(meter_sample_t){.status=meter_u16(m),.voltage_raw=meter_u16(m+4),
        .frequency_raw=meter_u16(m+6),.current_raw=meter_u32(m+12),.power_raw=meter_u32(m+16),
        .import_direction=(meter_u16(m)&(1u<<4))!=0,.import_raw=meter_u64(e),.export_raw=meter_u64(e+8)};
    return true;
}
void energy_init(energy_state_t *s, uint32_t profile_crc) {
    memset(s,0,sizeof(*s)); s->profile_crc=profile_crc; s->gaps=1; /* boot interval unknown */
}
static void gap(energy_state_t *s) { if (s->gaps<UINT32_MAX) s->gaps++; }
void energy_mark_gap(energy_state_t *s) { if(s->baseline)gap(s); s->baseline=false; }
bool energy_observe(energy_state_t *s, uint64_t raw, uint64_t now, uint32_t scale) {
    if (!scale || scale>1000000 || s->overflow) { s->baseline=false; return false; }
    if (!s->baseline) { s->last_raw=raw; s->last_ms=now; s->baseline=true; return false; }
    uint64_t before=s->last_raw, elapsed=now>=s->last_ms ? now-s->last_ms : 0;
    s->last_raw=raw; s->last_ms=now;
    if (raw<before || !elapsed || raw-before>UINT64_MAX/scale) { gap(s); return false; }
    uint64_t delta=(raw-before)*scale;
    /* Corruption plausibility ceiling only, NOT a certified relay/load rating: 50 kW. */
    if (elapsed > UINT64_MAX/50000 || delta > elapsed*50000/3600+1000) { gap(s); return false; }
    if (delta>UINT64_MAX-s->known_mwh) { s->overflow=true; gap(s); return false; }
    s->known_mwh+=delta; return true;
}
void energy_checkpoint(const energy_state_t *s, uint8_t out[ENERGY_CHECKPOINT_SIZE]) {
    memset(out,0,ENERGY_CHECKPOINT_SIZE); memcpy(out,"CSE1",4);
    put32(out+4,s->profile_crc); put64(out+8,s->known_mwh); put32(out+16,s->gaps);
    out[20]=s->overflow?1:0; put32(out+28,meter_crc32(out,28));
}
bool energy_restore(energy_state_t *s, const uint8_t *p, size_t n, uint32_t profile_crc) {
    if (!p || n!=ENERGY_CHECKPOINT_SIZE || memcmp(p,"CSE1",4) || meter_u32(p+4)!=profile_crc ||
        meter_crc32(p,28)!=meter_u32(p+28) || p[20]>1) return false;
    energy_init(s,profile_crc); s->known_mwh=meter_u64(p+8); s->gaps=meter_u32(p+16);
    s->overflow=p[20]!=0; gap(s); return true;
}
