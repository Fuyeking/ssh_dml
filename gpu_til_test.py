#!/usr/bin/env python
# encoding: utf-8
'''
@author: yeqing
@contact: 474387803@qq.com
@software: pycharm
@file: gpu_til_test.py
@time: 2019/10/20 22:52
@desc:
'''

import time
from threading import Thread

import GPUtil


class Monitor(Thread):
    def __init__(self, delay):
        super(Monitor, self).__init__()
        self.stopped = False
        self.delay = delay  # Time between calls to GPUtil
        self.start()

    def run(self):
        while not self.stopped:
            GPUtil.showUtilization()
            time.sleep(self.delay)

    def stop(self):
        self.stopped = True


# Instantiate monitor with a 10-second delay between updates
monitor = Monitor(4)
fp = open("gpu_log", "w")
fp.write("over test")
fp.write('\n')
fp.flush()
fp.closed
# Train, etc.
# Close monitor
monitor.stop()
