# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.interview.interaction import Interaction


class Confirmation(Interaction):
    """
    The last question, writes back the YAML file
    """

    def __init__(self):
        Interaction.__init__(self, required=False)
        self.__done = False

    def ask(self):
        print(self.context.get_content())
        message = "Press Enter to save," \
                  + " Ctrl-C to exit, or up arrow to correct" \
                  + " your answers. []"
        try:
            result = self.context.get_session().prompt(message)
            if result is not None:
                print("Writing file")
                self.__done = True
        except KeyboardInterrupt:
            # Ctrl-c gracefully exits
            pass

    def set_value(self, answer):
        pass

    def is_done(self):
        return self.__done
