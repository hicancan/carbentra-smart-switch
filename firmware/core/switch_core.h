#ifndef SWITCH_CORE_H
#define SWITCH_CORE_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#define SWITCH_CHANNELS 3
#define SWITCH_CACHE_SIZE 16
#define SWITCH_ID_MAX 48
#define SWITCH_BOOT_ID_LEN 32
#define SWITCH_COMMAND_TTL_MS 30000u
#define SWITCH_DEBOUNCE_MS 35u
#define SWITCH_MANUAL_HOLD_MS 900000u
#define SWITCH_MAX_MANUAL_HOLD_MS 3600000u
typedef enum { SWITCH_MODE_AUTO, SWITCH_MODE_MANUAL, SWITCH_MODE_MAINTENANCE, SWITCH_MODE_PROTECTED } switch_mode_t;

typedef struct {
    char id[SWITCH_ID_MAX + 1];
    char boot_id[SWITCH_BOOT_ID_LEN + 1];
    uint64_t seq;
    uint64_t expires_uptime_ms;
    uint8_t channel; /* external numbering: 1..3 */
    bool on;
} switch_command_t;
typedef enum {
    SWITCH_APPLIED, SWITCH_DUPLICATE, SWITCH_INVALID, SWITCH_WRONG_BOOT,
    SWITCH_EXPIRED, SWITCH_STALE_SEQUENCE, SWITCH_ID_CONFLICT,
    SWITCH_MANUAL_HOLD, SWITCH_MAINTENANCE, SWITCH_PROTECTED, SWITCH_NOT_COMMISSIONED, SWITCH_FAULT
} switch_result_t;
typedef struct {
    bool raw, stable, armed;
    uint64_t changed_at;
} switch_key_t;
typedef struct {
    char boot_id[SWITCH_BOOT_ID_LEN + 1];
    bool commanded[SWITCH_CHANNELS];
    bool commissioned, fault_latched, maintenance;
    uint8_t protected_mask;
    uint32_t manual_hold_ms;
    uint64_t hold_until_ms[SWITCH_CHANNELS];
    uint64_t local_event_seq, local_event_ms;
    uint8_t local_event_channel;
    switch_result_t local_event_result;
    switch_key_t keys[SWITCH_CHANNELS];
    uint64_t last_seq;
    switch_command_t cache[SWITCH_CACHE_SIZE];
    size_t cache_count, cache_next;
} switch_state_t;
void switch_init(switch_state_t *state, const char *boot_id);
void switch_configure(switch_state_t *state, bool commissioned, uint8_t protected_mask, bool maintenance, uint32_t hold_ms);
void switch_latch_fault(switch_state_t *state);
switch_mode_t switch_channel_mode(const switch_state_t *state, unsigned channel, uint64_t now_ms);
const char *switch_mode_name(switch_mode_t mode);
bool switch_valid_id(const char *id, size_t maximum);
bool switch_parse_u64(const char *text, uint64_t *value);
switch_result_t switch_apply(switch_state_t *state, const switch_command_t *cmd, uint64_t now_ms);
const char *switch_result_name(switch_result_t result);
/* Called with raw pressed=true. A held key at boot cannot energize a relay. */
bool switch_key_sample(switch_state_t *state, unsigned channel, bool pressed, uint64_t now_ms);
#endif
