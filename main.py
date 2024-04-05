import json
import socket
import logging
import pathlib
import mimetypes
import urllib.parse
from time import sleep
from threading import Thread
from datetime import datetime
from abc import ABC, abstractmethod
from http.server import HTTPServer, BaseHTTPRequestHandler

SOCKET_PORT = 5000
SOCKET_IP = "127.0.0.1"


logger = logging.getLogger()
stream_handler = logging.StreamHandler()
formatter = logging.Formatter("%(processName)s %(lineno)s %(message)s")

stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)
logger.setLevel(logging.DEBUG)


class HttpHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        pr_url = urllib.parse.urlparse(self.path)
        if pr_url.path == "/":
            self.send_html_file("index.html")
        elif pr_url.path == "/message":
            self.send_html_file("message.html")
        else:
            if pathlib.Path().joinpath(pr_url.path[1:]).exists():
                self.send_static()
            else:
                self.send_html_file("error.html", 404)

    def do_POST(self):
        data = self.rfile.read(int(self.headers["Content-Length"]))
        logger.debug(data)
       
        self.send_response(302)
        self.send_header("Location", "/")
        self.end_headers()
        self.save_to_socket_server(data)

    def send_static(self):
        self.send_response(200)
        mt = mimetypes.guess_type(self.path)
        if mt:
            self.send_header("Content-type", mt[0])
        else:
            self.send_header("Content-type", "text/plain")
        self.end_headers()
        with open(f".{self.path}", "rb") as file:
            self.wfile.write(file.read())

    def send_html_file(self, filename, status=200):
        self.send_response(status)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        with open(filename, "rb") as fd:
            self.wfile.write(fd.read())

    def save_to_socket_server(self, data):
        socket_UDP = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        server = SOCKET_IP, SOCKET_PORT
        socket_UDP.sendto(data, server)
        socket_UDP.close()


class ManagedServer(ABC):
    def __init__(self):
        self._is_running: bool = True

    def stop(self):
        self._is_running = False
        self._stop_server()

    def run(self):
        try:
            while self._is_running:
                self._run_server()
        except Exception:
            self._stop_server()

    @abstractmethod
    def _stop_server(self):
        pass

    @abstractmethod
    def _run_server(self):
        pass    

class ManagedHTTPServer(ManagedServer):
    def __init__(self, ip: str, port: int):
        super().__init__()
        self.__server_address = (ip, port)
        self.__http_server = HTTPServer(self.__server_address, HttpHandler)
    
    def _run_server(self):
        self.__http_server.serve_forever()

    def _stop_server(self):
        self.__http_server.server_close()


class ManagedUDPServer(ManagedServer):
    def __init__(self, ip: str, port: int):
        super().__init__()
        self.__server_address = (ip, port)
        self.__socket_UDP = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.__socket_UDP.bind(self.__server_address)

    def _run_server(self):
        data, address = self.__socket_UDP.recvfrom(1024)
        if data:
            data_parse = urllib.parse.unquote_plus(data.decode())
            logger.debug(data_parse)
            data_dict = {key: value for key, value in [el.split("=") for el in data_parse.split("&")]}
            json_dict = self.__read_data_from_json()
            self.__write_data_to_json(data_dict, json_dict)
    
    def __read_data_from_json(self) -> dict:
        json_dict = dict()
        with open("storage/data.json", "r") as file:
            json_dict.update(json.loads(file.read() or "{}"))
        return json_dict

    def __write_data_to_json(self, data: dict, json_dict: dict) -> None:
        with open("storage/data.json", "w") as file:
            json_dict[str(datetime.now())] = data
            json.dump(json_dict, file)

    def _stop_server(self):
        self.__socket_UDP.close()


class ManagedTCPServer(ManagedServer):
    pass


if __name__ == '__main__':
    http_server = ManagedHTTPServer("0.0.0.0", 3000)
    udp_server = ManagedUDPServer(SOCKET_IP, SOCKET_PORT)

    thread_1 = Thread(target=http_server.run, daemon=True)
    thread_2 = Thread(target=udp_server.run, daemon=True)

    thread_1.start()
    thread_2.start()

    try:
        while True:
            sleep(100)

    except KeyboardInterrupt:
        http_server.stop()
        udp_server.stop()
