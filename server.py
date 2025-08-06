import grpc
from concurrent import futures
import time
import serial

import hand_control_pb2
import hand_control_pb2_grpc

ROBOT_SERIAL_PORT = '/tmp/robot_write'
ROBOT_BAUD_RATE = 9600
GRPC_PORT = 50051

class HandControllerServicer(hand_control_pb2_grpc.HandControllerServicer):
    
    def __init__(self):
        self.robot_serial = None
        self.message_count = 0
        self.total_e2e_latency = 0
        self.start_time = None
        self._initialize_serial()
    
    def _initialize_serial(self):
        try:
            self.robot_serial = serial.Serial(ROBOT_SERIAL_PORT, ROBOT_BAUD_RATE, timeout=1)
            print(f"Robot bağlandı: {ROBOT_SERIAL_PORT}")
        except serial.SerialException as e:
            print(f"Robot bağlantı hatası: {e}")
    
    def StreamHandData(self, request_iterator, context):
        print("Client ile bağlantı kuruldu.")
        self.start_time = time.time()
        
        try:
            for hand_data in request_iterator:
                self._process_data(hand_data)
        except Exception as e:
            print(f"Hata: {e}")
        
        if self.message_count > 0:
            total_time = time.time() - self.start_time
            avg_e2e_latency = self.total_e2e_latency / self.message_count
            throughput = self.message_count / total_time
            print(f"Toplam: {self.message_count} mesaj, Süre: {total_time:.2f}s, Ort E2E: {avg_e2e_latency:.2f}ms, Throughput: {throughput:.1f} msg/s")
        
        return hand_control_pb2.Ack(success=True)
    
    def _process_data(self, hand_data):
        self.message_count += 1
        
        # End-to-end latency hesapla
        current_time_ms = int(time.time() * 1000)
        end_to_end_latency = current_time_ms - hand_data.timestamp_ms
        self.total_e2e_latency += end_to_end_latency
        avg_e2e_latency = self.total_e2e_latency / self.message_count
        
        # Servo değerleri al
        servo_values = hand_data.finger_values
        
        # Arduino'ya gönder
        if self.robot_serial and self.robot_serial.is_open:
            command = ",".join(map(str, servo_values)) + "\n"
            self.robot_serial.write(command.encode('utf-8'))
        
        # Throughput hesapla
        elapsed = time.time() - self.start_time
        throughput = self.message_count / elapsed if elapsed > 0 else 0
        
        # Her 50 mesajda bir göster
        if self.message_count % 50 == 0:
            print(f"SERVER #{self.message_count:04d} | {throughput:.1f} msg/s | E2E: {end_to_end_latency}ms | Ort E2E: {avg_e2e_latency:.1f}ms | Servolar: {servo_values}")

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
