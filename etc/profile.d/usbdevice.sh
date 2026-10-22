#!/bin/sh
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

# Prefer bash for adb shell when available; fall back to /bin/sh.
if [ -z "${ADBD_SHELL:-}" ]; then
    ADBD_SHELL=$(command -v bash 2>/dev/null || true)
    export ADBD_SHELL="${ADBD_SHELL:-/bin/sh}"
fi

# USB identity and gadget tuning are configured in /etc/default/adbd-gadget.
# Examples (all optional, sensible defaults apply):
#   ADBD_GADGET_IDVENDOR=0x18d1
#   ADBD_GADGET_IDPRODUCT=0x4ee7
#   ADBD_GADGET_SERIAL=0123456789
