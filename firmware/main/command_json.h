#ifndef SWITCH_COMMAND_JSON_H
#define SWITCH_COMMAND_JSON_H
#include "switch_core.h"
bool command_json_decode(const char *data,size_t n,switch_command_t *out);
#endif
