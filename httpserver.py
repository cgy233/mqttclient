import ubinascii
import socket
import ujson
import time
import machine
from json_util import status, saveJson

def parseHeader(headerLine):
    kwDict = {}

    # print(headerLine)
    # time.sleep(1)  # wait 1 seconds 
    bytesline = headerLine
    headerLine = headerLine.decode('ascii')

    if headerLine.find('?') >= 0:
        _percent_pat = compile(b'%[A-Fa-f0-9][A-Fa-f0-9]')
        hex_to_byte = lambda match_ret: \
                  ubinascii.unhexlify(match_ret.group(0).replace(b'%', b'').decode('ascii'))

        bytesline = _percent_pat.sub(hex_to_byte, bytesline)
        headerLine = bytesline.decode('ascii')

        # print('1', headerLine)
        headerLine = headerLine.split('?')[1]
        # print('2', headerLine)
        lists = headerLine.split('&')
        for kw in lists:
            kwlist = kw.split('=')
            kwDict[kwlist[0]] =  kwlist[1]
            # print('3', kwlist[1])

        return kwDict

def httpServer():
    global status
    bodyLen = None
    template = """HTTP/1.1 200 OK Content-Length: {length}{json}"""
    reqDict = {}
    cb = None
    needReset = False
    addr = socket.getaddrinfo('0.0.0.0', int(status['gateway_port']))[0][-1]

    s = socket.socket()
    s.bind(addr)
    s.listen(1)

    print('listening on', addr)

    while True:
        cl, addr = s.accept()
        # print('client connected from', addr)
        # 
        cl_file=cl.makefile('rwb',0)
        while True:
            line = cl_file.readline()
            ret = parseHeader(line)

            if ret:
                reqDict = ret

            if (not line) or (line == b'\r\n'):
                break

        if 'callbacks' in reqDict.keys():
            cb = reqDict['callbacks']
            # print('4', cb)
        
        for key in status:
            if key in reqDict.keys() and status[key] != reqDict[key] and key != 'dname':
                status[key] = reqDict[key]
                needReset = True
                print('5', key)

        saveJson()
        reqDict = {}

        if cb:
            data = "{}('{}')" .format(cb, ujson.dumps(status))
            cb = None
        else:
            data = ''
        
        response = template.format(length=len(data), json=data)
        print(data)
        time.sleep(1)  # wait 1 seconds
        cl.send(response)
        cl.close()

        if needReset:
            time.sleep(1)  # wait 1 seconds                
            machine.reset()