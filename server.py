import grpc
from concurrent import futures
import time
import threading
import serial

import hand_control_pb2
import hand_control_pb2_grpc

ROBOT_SERIAL_PORT = '/tmp/robot_write'
ROBOT_BAUD_RATE = 9600
GRPC_PORT = 50051

class HandControllerServicer(hand_control_pb2_grpc.HandControllerServicer):
    
    def __init__(self):
        self.robot_serial = None
        self._serial_lock = threading.Lock()
        self._last_sent_values = None
        self._initialize_serial()
    
    def _initialize_serial(self):
        try:
            self.robot_serial = serial.Serial(ROBOT_SERIAL_PORT, ROBOT_BAUD_RATE, timeout=1)
            print(f"Robot bağlandı: {ROBOT_SERIAL_PORT}")
        except serial.SerialException as e:
            print(f"Robot bağlantı hatası: {e}")
    
    def StreamHandData(self, request_iterator, context):
        print("Client ile bağlantı kuruldu.")
        start_time = time.time()
        message_count = 0

        try:
            for hand_data in request_iterator:
                message_count += 1

                servo_values = self._quantize_servo_values(hand_data.finger_values)

                if self._last_sent_values == tuple(servo_values):
                    continue

                self._send_to_serial(servo_values)
                self._last_sent_values = tuple(servo_values)

                if message_count % 50 == 0:
                    elapsed = time.time() - start_time
                    throughput = message_count / elapsed if elapsed > 0 else 0
                    print(
                        f"SERVER #{message_count:04d} | {throughput:.1f} msg/s | Servolar: {servo_values}"
                    )
        except Exception as e:
            print(f"Hata: {e}")
        
        if message_count > 0:
            total_time = time.time() - start_time
            throughput = message_count / total_time if total_time > 0 else 0
            print(
                f"Toplam: {message_count} mesaj, Süre: {total_time:.2f}s, "
                f"Throughput: {throughput:.1f} msg/s"
            )
        
        return hand_control_pb2.Ack(success=True)

    def _send_to_serial(self, servo_values):
        if not self.robot_serial or not self.robot_serial.is_open:
            return

        command = ",".join(map(str, servo_values)) + "\n"

        try:
            with self._serial_lock:
                self.robot_serial.write(command.encode('utf-8'))
        except serial.SerialException as e:
            print(f"Seri yazma hatası: {e}")

    def _quantize_servo_values(self, values):
        allowed_positions = (500, 1000, 1500)
        # Clamp each incoming value to the nearest allowed servo position.
        return [min(allowed_positions, key=lambda target: abs(value - target)) for value in values]

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    hand_control_pb2_grpc.add_HandControllerServicer_to_server(HandControllerServicer(), server)
    server.add_insecure_port(f'[::]:{GRPC_PORT}')
    server.start()
    
    print(f"Server başladı - Port: {GRPC_PORT}")
    print("Client bekleniyor...")
    
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        print("Server kapatılıyor...")
        server.stop(0)

if __name__ == '__main__':
    serve()
