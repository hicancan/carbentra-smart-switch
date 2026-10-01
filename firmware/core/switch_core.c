#include "switch_core.h"
#include <string.h>

bool switch_valid_id(const char *id, size_t maximum) {
    if (!id || !id[0]) return false;
    size_t n = 0;
    for (; n <= maximum && id[n]; n++) {
        char c = id[n];
        if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
              (c >= '0' && c <= '9') || c == '-' || c == '_')) return false;
    }
    return n <= maximum;
}
bool switch_parse_u64(const char *text, uint64_t *value) {
    if (!text || !*text || !value) return false;
    uint64_t n = 0;
    for (size_t i = 0; text[i]; i++) {
        if (i >= 20 || text[i] < '0' || text[i] > '9') return false;
        uint8_t digit = (uint8_t)(text[i] - '0');
        if (n > (UINT64_MAX - digit) / 10) return false;
        n = n * 10 + digit;
    }
    *value = n;
    return true;
}
void switch_init(switch_state_t *s, const char *boot_id) {
    memset(s, 0, sizeof(*s));
    if (boot_id && strlen(boot_id) == SWITCH_BOOT_ID_LEN)
        memcpy(s->boot_id, boot_id, SWITCH_BOOT_ID_LEN);
    s->manual_hold_ms = SWITCH_MANUAL_HOLD_MS;
    /* Keys start pressed and unarmed; stable release must be observed first. */
    for (unsigned i = 0; i < SWITCH_CHANNELS; i++) s->keys[i].raw = s->keys[i].stable = true;
}
void switch_configure(switch_state_t *s, bool commissioned, uint8_t protected_mask, bool maintenance, uint32_t hold_ms) {
    s->commissioned = commissioned;
    s->protected_mask = protected_mask & 7u;
    s->maintenance = maintenance;
    s->manual_hold_ms = hold_ms && hold_ms <= SWITCH_MAX_MANUAL_HOLD_MS ? hold_ms : SWITCH_MANUAL_HOLD_MS;
    if (!commissioned || maintenance) for (unsigned i=0;i<SWITCH_CHANNELS;i++) s->commanded[i]=false;
}
void switch_latch_fault(switch_state_t *s) {
    s->fault_latched=true;
    for(unsigned i=0;i<SWITCH_CHANNELS;i++) s->commanded[i]=false;
}
switch_mode_t switch_channel_mode(const switch_state_t *s, unsigned channel, uint64_t now) {
    if (s->maintenance) return SWITCH_MODE_MAINTENANCE;
    if (channel >= SWITCH_CHANNELS || (s->protected_mask & (1u << channel))) return SWITCH_MODE_PROTECTED;
    return now < s->hold_until_ms[channel] ? SWITCH_MODE_MANUAL : SWITCH_MODE_AUTO;
}
const char *switch_mode_name(switch_mode_t mode) {
    static const char *names[]={"auto","manual","maintenance","protected"};
    return (unsigned)mode < 4 ? names[mode] : "protected";
}
static bool same_command(const switch_command_t *a, const switch_command_t *b) {
    return a->seq == b->seq && a->channel == b->channel && a->on == b->on &&
           a->expires_uptime_ms == b->expires_uptime_ms && !strcmp(a->boot_id, b->boot_id);
}
switch_result_t switch_apply(switch_state_t *s, const switch_command_t *c, uint64_t now) {
    if (!c || !switch_valid_id(c->id, SWITCH_ID_MAX) || c->channel < 1 ||
        c->channel > SWITCH_CHANNELS || !c->seq) return SWITCH_INVALID;
    if (memcmp(c->boot_id, s->boot_id, SWITCH_BOOT_ID_LEN + 1)) return SWITCH_WRONG_BOOT;
    for (size_t i = 0; i < s->cache_count; i++) {
        if (!strcmp(c->id, s->cache[i].id))
            return same_command(c, &s->cache[i]) ? SWITCH_DUPLICATE : SWITCH_ID_CONFLICT;
    }
    if (c->expires_uptime_ms <= now || c->expires_uptime_ms - now > SWITCH_COMMAND_TTL_MS)
        return SWITCH_EXPIRED;
    if (c->seq <= s->last_seq) return SWITCH_STALE_SEQUENCE;
    if (s->fault_latched) return SWITCH_FAULT;
    switch_mode_t mode=switch_channel_mode(s,c->channel-1,now);
    if (mode==SWITCH_MODE_MAINTENANCE) return SWITCH_MAINTENANCE;
    if (mode==SWITCH_MODE_PROTECTED) return SWITCH_PROTECTED;
    if (mode==SWITCH_MODE_MANUAL) return SWITCH_MANUAL_HOLD;
    if (c->on && !s->commissioned) return SWITCH_NOT_COMMISSIONED;
    s->commanded[c->channel - 1] = c->on;
    s->last_seq = c->seq;
    s->cache[s->cache_next] = *c;
    s->cache_next = (s->cache_next + 1) % SWITCH_CACHE_SIZE;
    if (s->cache_count < SWITCH_CACHE_SIZE) s->cache_count++;
    return SWITCH_APPLIED;
}
const char *switch_result_name(switch_result_t result) {
    static const char *names[] = {"commanded", "duplicate", "invalid_command", "wrong_boot", "expired", "stale_sequence", "id_conflict", "manual_hold", "maintenance", "protected", "not_commissioned", "fault_latched"};
    return (unsigned)result < sizeof(names)/sizeof(names[0]) ? names[result] : "invalid_command";
}
bool switch_key_sample(switch_state_t *s, unsigned channel, bool pressed, uint64_t now) {
    if (channel >= SWITCH_CHANNELS) return false;
    switch_key_t *key = &s->keys[channel];
    if (pressed != key->raw) { key->raw = pressed; key->changed_at = now; }
    if (now < key->changed_at || now - key->changed_at < SWITCH_DEBOUNCE_MS || key->stable == key->raw) return false;
    key->stable = key->raw;
    if (!key->stable) key->armed = true;
    else if (key->armed) {
        /* Record a real debounced press even when safety blocks energizing. */
        if(s->local_event_seq != UINT64_MAX) s->local_event_seq++;
        s->local_event_ms=now;s->local_event_channel=(uint8_t)(channel+1);
        s->hold_until_ms[channel]=now > UINT64_MAX-s->manual_hold_ms ? UINT64_MAX : now+s->manual_hold_ms;
        bool on=!s->commanded[channel];
        s->local_event_result=s->fault_latched ? SWITCH_FAULT : s->maintenance ? SWITCH_MAINTENANCE :
            on && !s->commissioned ? SWITCH_NOT_COMMISSIONED : SWITCH_APPLIED;
        /* Protected channels reject automation, but retain physical local control. */
        if(s->local_event_result==SWITCH_APPLIED)s->commanded[channel]=on;
        return true;
    }
    return false;
}
