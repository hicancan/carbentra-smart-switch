#ifndef SWITCH_DEVICE_CONFIG_H
#define SWITCH_DEVICE_CONFIG_H
#include <stdbool.h>
#include <stdint.h>
#include "meter.h"
typedef struct {
    char device_id[33], calibration_id[49];
    char *broker_uri, *ca_pem, *client_cert, *client_key;
    uint8_t salt[16], verifier[384], meter_profile[MCP_PROFILE_SIZE];
    uint32_t voltage_uv, current_ua, power_mw, energy_mwh, profile_crc;
    bool mqtt_ready, provisioning_ready, calibration_ready;
    bool commissioned, maintenance;
    uint8_t protected_mask;
    uint32_t manual_hold_ms;
} device_config_t;
void device_config_load(device_config_t *config);
#endif
