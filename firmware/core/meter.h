#ifndef SWITCH_METER_H
#define SWITCH_METER_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#define MCP_MAX_DATA 32
#define MCP_PROFILE_START 0x0050
#define MCP_PROFILE_SIZE (0x00E2 - MCP_PROFILE_START)
#define ENERGY_CHECKPOINT_SIZE 32
/* Host commands have big-endian address; returned register bytes are little-endian. */
size_t mcp_read_request(uint16_t address, uint8_t count, uint8_t output[8]);
bool mcp_read_response(const uint8_t *frame, size_t length, uint8_t count, uint8_t *data);
uint16_t meter_u16(const uint8_t *p);
uint32_t meter_u32(const uint8_t *p);
uint64_t meter_u64(const uint8_t *p);
uint32_t meter_crc32(const uint8_t *p, size_t n);
typedef struct {
    uint16_t status, voltage_raw, frequency_raw;
    uint32_t current_raw, power_raw;
    bool import_direction;
    uint64_t import_raw, export_raw;
} meter_sample_t;
bool meter_decode(const uint8_t measurements[28], const uint8_t energy[16], meter_sample_t *out);
typedef struct {
    uint64_t known_mwh, last_raw, last_ms;
    uint32_t gaps, profile_crc;
    bool baseline, overflow;
} energy_state_t;
void energy_init(energy_state_t *s, uint32_t profile_crc);
/* Never extrapolates across reboot, a counter rollback, an implausible jump or unknown scaling. */
bool energy_observe(energy_state_t *s, uint64_t raw, uint64_t now_ms, uint32_t mwh_per_unit);
void energy_mark_gap(energy_state_t *s);
void energy_checkpoint(const energy_state_t *s, uint8_t output[ENERGY_CHECKPOINT_SIZE]);
bool energy_restore(energy_state_t *s, const uint8_t *data, size_t length, uint32_t profile_crc);
#endif
