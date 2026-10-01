#ifndef SWITCH_APP_STATE_H
#define SWITCH_APP_STATE_H
#include "switch_core.h"
#include "meter.h"
#include <stdbool.h>
typedef struct {
    switch_state_t control;
    meter_sample_t meter;
    energy_state_t energy;
    uint64_t uptime_ms, meter_observed_ms;
    bool meter_online, calibrated, energy_storage_ok;
} app_snapshot_t;
void app_snapshot(app_snapshot_t *out);
switch_result_t app_command(const switch_command_t *command);
#endif
