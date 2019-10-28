#!/usr/bin/env python
# encoding: utf-8
import math
import multiprocessing as mp
import os
import random
import time
from datetime import datetime
from functools import wraps

import paramiko


def timethis(func):
    """
    时间装饰器，计算函数执行所消耗的时间
    :param func:
    :return:
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        start = datetime.now()
        result = func(*args, **kwargs)
        end = datetime.now()
        print(func.__name__, end - start)
        return result

    return wrapper


class GPU(object):
    def __init__(self, ID, uuid, load, memoryTotal, memoryUsed, memoryFree, driver, gpu_name, serial, display_mode,
                 display_active, temp_gpu):
        self.id = ID
        self.uuid = uuid
        self.load = load
        self.memoryUtil = float(memoryUsed) / float(memoryTotal)
        self.memoryTotal = memoryTotal
        self.memoryUsed = memoryUsed
        self.memoryFree = memoryFree
        self.driver = driver
        self.name = gpu_name
        self.serial = serial
        self.display_mode = display_mode
        self.display_active = display_active
        self.temperature = temp_gpu


class SSHManager(object):
    def __init__(self, host, port, usr, passwd):
        self._host = host
        self._usr = usr
        self._password = passwd
        self._port = port
        self._ssh = None
        self._sftp = None
        self._sftp_connect()
        self._ssh_connect()

    def __del__(self):
        if self._ssh:
            self._ssh.close()
        if self._sftp:
            self._sftp.close()

    def _sftp_connect(self):
        try:
            transport = paramiko.Transport((self._host, self._port))
            transport.connect(username=self._usr, password=self._password)
            self._sftp = paramiko.SFTPClient.from_transport(transport)
        except Exception as e:
            raise RuntimeError("sftp connect failed [%s]" % str(e))

    def _ssh_connect(self):
        try:
            # 创建ssh对象
            self._ssh = paramiko.SSHClient()
            # 允许连接不在know_hosts文件中的主机
            self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            # 连接服务器
            self._ssh.connect(hostname=self._host,
                              port=self._port,
                              username=self._usr,
                              password=self._password,
                              timeout=5)
        except Exception:
            raise RuntimeError("ssh connected to [host:%s, usr:%s, passwd:%s] failed" %
                               (self._host, self._usr, self._password))

    def ssh_exec_cmd(self, cmd, path='~'):
        """
        通过ssh连接到远程服务器，执行给定的命令
        :param cmd: 执行的命令
        :param path: 命令执行的目录
        :return: 返回结果
        """
        cmd = 'cd ' + path + ';' + cmd
        try:
            result = self._exec_command(cmd)
            print(result)
        except Exception:
            raise RuntimeError('exec cmd [%s] failed' % cmd)

    def ssh_exec_cmd_shell(self, cmd):
        ssh = self._ssh.get_transport().open_session()
        ssh.get_pty()
        ssh.invoke_shell()
        # 执行指令
        ssh.sendall(cmd + "\n")
        time.sleep(0.5)
        result = ssh.recv(102400)
        result = result.decode(encoding='UTF-8', errors='strict')
        return result

    def __to_str(self, bytes_or_str):
        """
        把byte类型转换为str
        :param bytes_or_str:
        :return:
        """
        if isinstance(bytes_or_str, bytes):
            value = bytes_or_str.decode('utf-8')
        else:
            value = bytes_or_str
        return value

    @timethis
    def upload_file(self, local_file, remote_file):
        """
        通过sftp上传本地文件到远程
        :param local_file:
        :param remote_file:
        :return:
        """
        try:
            self._sftp.put(local_file, remote_file)
        except Exception as e:
            raise RuntimeError('upload failed [%s]' % str(e))

    def download_file(self, target_path, local_path):

        try:
            # 连接，下载
            while True:
                result = self._exec_command("find " + target_path)
                if len(result) != 0:
                    break
            self._sftp.get(target_path, local_path)
        except Exception as e:
            raise RuntimeError('down failed [%s]' % str(e))

    def _exec_command(self, cmd):
        """
        通过ssh执行远程命令
        :param cmd:
        :return:
        """
        try:
            stdin, stdout, stderr = self._ssh.exec_command(cmd)
            return self.__to_str(stdout.read())
        except Exception as e:
            raise RuntimeError('Exec command [%s] failed' % str(cmd))

    # 获取计算机节点的GPU信息
    def getGPUs(self):
        cmd = "nvidia-smi" + " " + "--query-gpu=index,uuid,utilization.gpu,memory.total,memory.used,memory.free,driver_version,name,gpu_serial,display_active,display_mode,temperature.gpu" + " " + "--format=csv,noheader,nounits"
        output = self._exec_command(cmd)
        lines = output.split('\n')
        numDevices = len(lines) - 1
        GPUs = []
        for g in range(numDevices):
            line = lines[g]
            vals = line.split(', ')
            for i in range(12):
                if (i == 0):
                    deviceIds = int(vals[i])
                elif (i == 1):
                    uuid = vals[i]
                elif (i == 2):
                    gpuUtil = self._safe_float_cast(vals[i]) / 100
                elif (i == 3):
                    memTotal = self._safe_float_cast(vals[i])
                elif (i == 4):
                    memUsed = self._safe_float_cast(vals[i])
                elif (i == 5):
                    memFree = self._safe_float_cast(vals[i])
                elif (i == 6):
                    driver = vals[i]
                elif (i == 7):
                    gpu_name = vals[i]
                elif (i == 8):
                    serial = vals[i]
                elif (i == 9):
                    display_active = vals[i]
                elif (i == 10):
                    display_mode = vals[i]
                elif (i == 11):
                    temp_gpu = self._safe_float_cast(vals[i]);
            GPUs.append(
                GPU(deviceIds, uuid, gpuUtil, memTotal, memUsed, memFree, driver, gpu_name, serial, display_mode,
                    display_active, temp_gpu))
        return GPUs  # (deviceIds, gpuUtil, memUtil)

    # 根据选项获取GPU资源
    def get_available_ids(self, order='memory', limit=1, maxLoad=0.5, maxMemory=0.5, memoryFree=0, includeNan=False,
                          excludeID=[],
                          excludeUUID=[]):
        # order = first | last | random | load | memory
        #    first --> select the GPU with the lowest ID (DEFAULT)
        #    last --> select the GPU with the highest ID
        #    random --> select a random available GPU
        #    load --> select the GPU with the lowest load
        #    memory --> select the GPU with the most memory available
        # limit = 1 (DEFAULT), 2, ..., Inf
        #     Limit sets the upper limit for the number of GPUs to return. E.g. if limit = 2, but only one is available, only one is returned.
        # Get device IDs, load and memory usage
        GPUs = self.getGPUs()
        # Determine, which GPUs are available
        GPUavailability = self._judge_available(GPUs, maxLoad=maxLoad, maxMemory=maxMemory, memoryFree=memoryFree,
                                                includeNan=includeNan, excludeID=excludeID, excludeUUID=excludeUUID)
        availAbleGPUindex = [idx for idx in range(0, len(GPUavailability)) if (GPUavailability[idx] == 1)]
        # Discard unavailable GPUs
        GPUs = [GPUs[g] for g in availAbleGPUindex]
        # Sort available GPUs according to the order argument
        if (order == 'first'):
            GPUs.sort(key=lambda x: float('inf') if math.isnan(x.id) else x.id, reverse=False)
        elif (order == 'last'):
            GPUs.sort(key=lambda x: float('-inf') if math.isnan(x.id) else x.id, reverse=True)
        elif (order == 'random'):
            GPUs = [GPUs[g] for g in random.sample(range(0, len(GPUs)), len(GPUs))]
        elif (order == 'load'):
            GPUs.sort(key=lambda x: float('inf') if math.isnan(x.load) else x.load, reverse=False)
        elif (order == 'memory'):
            GPUs.sort(key=lambda x: float('inf') if math.isnan(x.memoryUtil) else x.memoryUtil, reverse=False)
        # Extract the number of desired GPUs, but limited to the total number of available GPUs
        GPUs = GPUs[0:min(limit, len(GPUs))]
        # Extract the device IDs from the GPUs and return them
        deviceIds = [gpu.id for gpu in GPUs]
        return deviceIds

    def _judge_available(self, GPUs, maxLoad=0.5, maxMemory=0.5, memoryFree=0, includeNan=False, excludeID=[],
                         excludeUUID=[]):
        # Determine, which GPUs are available
        GPUavailability = [
            1 if (gpu.memoryFree >= memoryFree) and (gpu.load < maxLoad or (includeNan and math.isnan(gpu.load))) and (
                    gpu.memoryUtil < maxMemory or (includeNan and math.isnan(gpu.memoryUtil))) and (
                         (gpu.id not in excludeID) and (gpu.uuid not in excludeUUID)) else 0 for gpu in GPUs]
        return GPUavailability

    def _safe_float_cast(self, str):
        try:
            number = float(str)
        except ValueError:
            number = float('nan')
        return number


class ComputingNode(object):
    def __init__(self, ip, port, user, pwd):
        self.host = ip
        self.port = port
        self.user = user
        self.pwd = pwd


if __name__ == '__main__':
    computing_nodes = []  # 存放所有计算节点的信息
    #node1 = ComputingNode("192.168.0.56", 22, "root", "lg123456")
    #computing_nodes.append(node1)
    node2 = ComputingNode("202.115.103.60", 10022, "yeqing", "qweasd234")
    computing_nodes.append(node2)
    for node in computing_nodes:
        ssh = SSHManager(node.host, node.port, node.user, node.pwd)
        gpu_ids = ssh.get_available_ids()
        if len(gpu_ids) > 0:
            print(ssh.get_available_ids())
            ssh.upload_file("./gpu_til_test.py", "gpu_til_test.py")
            ssh.ssh_exec_cmd_shell("nohup python gpu_til_test.py &")
            ssh.download_file("gpu_log", node.host + "log.txt")
