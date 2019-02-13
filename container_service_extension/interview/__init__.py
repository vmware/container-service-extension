# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import traceback

debugLevel = True
next_question = None
question_stack = []


def debug(message):
    global debugLevel
    if debugLevel:
        print("DEBUG:" + str(message))


def debug_traceback():
    global debugLevel
    if debugLevel:
        traceback.print_exc()
