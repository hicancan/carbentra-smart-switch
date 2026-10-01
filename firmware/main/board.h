#ifndef SWITCH_BOARD_H
#define SWITCH_BOARD_H
/* Contract with electronics: ESP32-C3-MINI-1-N4X, cold domain only. */
#define RELAY1_GPIO 0
#define RELAY2_GPIO 1
#define RELAY3_GPIO 3
#define KEY1_GPIO 4
#define KEY2_GPIO 5
#define KEY3_GPIO 6
#define METER_RX_GPIO 7
#define METER_TX_GPIO 10
#define METER_UART 1
#define METER_BAUD 9600
#endif
