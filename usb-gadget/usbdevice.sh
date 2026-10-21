#!/bin/sh

# The standalone Linux adbd defaults to /bin/sh; use bash for adb shell.
export ADBD_SHELL=/bin/bash

# USB identity and gadget tuning are configured in /etc/default/adbd-gadget.
# Examples (all optional, sensible defaults apply):
#   ADBD_GADGET_IDVENDOR=0x18d1
#   ADBD_GADGET_IDPRODUCT=0x4ee7
#   ADBD_GADGET_SERIAL=0123456789
