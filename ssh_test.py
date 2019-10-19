#!/usr/bin/env python
# encoding: utf-8
'''
@author: yeqing
@contact: 474387803@qq.com
@software: pycharm
@file: ssh_test.py
@time: 2019/10/19 12:07
@desc:
'''
import paramiko

s = paramiko.SSHClient()
s.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # 允许连接不在know_hosts文件中的主机
s.connect("202.115.103.60", 10022, "yeqing", "qweasd234")
execmd = 'ls'  # 需要输入的命令
stdin, stdout, stderr = s.exec_command(execmd)
print(stdout.read())
s.close()

