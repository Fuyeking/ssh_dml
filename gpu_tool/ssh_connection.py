#!/usr/bin/env python
# encoding: utf-8
'''
@author: yeqing
@contact: 474387803@qq.com
@software: pycharm
@file: ssh_connection.py.py
@time: 2019/10/19 15:02
@desc:
'''

import math
import random

import paramiko


class GPU:
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


class SSHConnection(object):

    def __init__(self, host_dict):
        self.host = host_dict['host']
        self.port = host_dict['port']
        self.username = host_dict['username']
        self.pwd = host_dict['pwd']
        self.__k = None
        self.__transport = None

    def connect(self):
        transport = paramiko.Transport((self.host, self.port))
        transport.connect(username=self.username, password=self.pwd)
        self.__transport = transport

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

    def close(self):
        self.__transport.close()

    def run_cmd(self, command):
        """
         执行shell命令,返回字典
         return {'color': 'red','res':error}或
         return {'color': 'green', 'res':res}
        :param command:
        :return:
        """
        ssh = paramiko.SSHClient()
        ssh._transport = self.__transport
        # 执行命令
        stdin, stdout, stderr = ssh.exec_command(command)
        # 获取命令结果
        res = self.__to_str(stdout.read())
        # 获取错误信息
        error = self.__to_str(stderr.read())
        # 如果有错误信息，返回error
        # 否则返回res
        if error.strip():
            return {'color': 'red', 'res': error}
        else:
            return {'color': 'green', 'res': res}

    def safeFloatCast(self, strNumber):
        try:
            number = float(strNumber)
        except ValueError:
            number = float('nan')
        return number

    def getGPUs(self):
        '''
        if platform.system() == "Windows":
            # If the platform is Windows and nvidia-smi
            # could not be found from the environment path,
            # try to find it from system drive with default installation path
            nvidia_smi = spawn.find_executable('nvidia-smi')
            if nvidia_smi is None:
                nvidia_smi = "%s\\Program Files\\NVIDIA Corporation\\NVSMI\\nvidia-smi.exe" % os.environ['systemdrive']
        else:
            nvidia_smi = "nvidia-smi"

        # Get ID, processing and memory utilization for all GPUs
        try:
            p = Popen([nvidia_smi,
                       "--query-gpu=index,uuid,utilization.gpu,memory.total,memory.used,memory.free,driver_version,name,gpu_serial,display_active,display_mode,temperature.gpu",
                       "--format=csv,noheader,nounits"], stdout=PIPE)
            stdout, stderror = p.communicate()
        except:
            return []
        output = stdout.decode('UTF-8')
        '''
        cmd = "nvidia-smi " + "--query-gpu=index,uuid,utilization.gpu,memory.total,memory.used,memory.free,driver_version,name,gpu_serial,display_active,display_mode,temperature.gpu " + "--format=csv,noheader,nounits"
        cmd_return = self.run_cmd(cmd)
        output = cmd_return['res']
        lines = output.split('\n')
        print(lines)
        numDevices = len(lines) - 1
        GPUs = []
        for g in range(numDevices):
            line = lines[g]
            # print(line)
            vals = line.split(', ')
            # print(vals)
            for i in range(12):
                # print(vals[i])
                if (i == 0):
                    deviceIds = int(vals[i])
                elif (i == 1):
                    uuid = vals[i]
                elif (i == 2):
                    gpuUtil = self.safeFloatCast(vals[i]) / 100
                elif (i == 3):
                    memTotal = self.safeFloatCast(vals[i])
                elif (i == 4):
                    memUsed = self.safeFloatCast(vals[i])
                elif (i == 5):
                    memFree = self.safeFloatCast(vals[i])
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
                    temp_gpu = self.safeFloatCast(vals[i]);
            GPUs.append(
                GPU(deviceIds, uuid, gpuUtil, memTotal, memUsed, memFree, driver, gpu_name, serial, display_mode,
                    display_active, temp_gpu))
        return GPUs  # (deviceIds, gpuUtil, memUtil)

    def getAvailable(self, order='first', limit=1, maxLoad=0.5, maxMemory=0.5, memoryFree=0, includeNan=False,
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
        GPUavailability = self.getAvailability(GPUs, maxLoad=maxLoad, maxMemory=maxMemory, memoryFree=memoryFree,
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

    def getAvailability(self, GPUs, maxLoad=0.5, maxMemory=0.5, memoryFree=0, includeNan=False, excludeID=[],
                        excludeUUID=[]):
        # Determine, which GPUs are available
        GPUavailability = [
            1 if (gpu.memoryFree >= memoryFree) and (gpu.load < maxLoad or (includeNan and math.isnan(gpu.load))) and (
                    gpu.memoryUtil < maxMemory or (includeNan and math.isnan(gpu.memoryUtil))) and (
                         (gpu.id not in excludeID) and (gpu.uuid not in excludeUUID)) else 0 for gpu in GPUs]
        return GPUavailability

    def upload(self, local_path, target_path):
        # 连接，上传
        sftp = paramiko.SFTPClient.from_transport(self.__transport)
        # 将location.py 上传至服务器 /tmp/test.py
        sftp.put(local_path, target_path, confirm=True)
        # print(os.stat(local_path).st_mode)
        # 增加权限
        # sftp.chmod(target_path, os.stat(local_path).st_mode)
        sftp.chmod(target_path, 0o755)  # 注意这里的权限是八进制的，八进制需要使用0o作为前缀

    def download(self, target_path, local_path):
        # 连接，下载
        sftp = paramiko.SFTPClient.from_transport(self.__transport)
        sftp.get(target_path, local_path)

    # 销毁
    def __del__(self):
        self.close()


if __name__ == '__main__':
    host = {}
    host['host'] = "202.115.103.60"
    host['port'] = 22
    host['username'] = "*"
    host['pwd'] = "qweasd234"
    ssh_conn = SSHConnection(host)
    ssh_conn.connect()
    # cmd = "nvidia-smi" + "--query-gpu=index,uuid,utilization.gpu,memory.total,memory.used,memory.free,driver_version,name,gpu_serial,display_active,display_mode,temperature.gpu" + "--format=csv,noheader,nounits"
    # cmd_str = ssh_conn.run_cmd(cmd)
    print(ssh_conn.getGPUs())
    print(ssh_conn.getAvailable(limit=3))
# print(return_str.split('\n'))
