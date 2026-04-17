## GameAPI.gd — HTTP-клиент к echo-sim server.py
extends Node

signal response_done(narrative: String, state: Dictionary)
signal state_received(state: Dictionary)
signal error_occurred(message: String)
signal connected(ok: bool)

var server_url: String = "http://127.0.0.1:8080"

var _http_cmd: HTTPRequest
var _http_check: HTTPRequest
var _http_reset: HTTPRequest

const HEADERS = [
	"Content-Type: application/json",
	"ngrok-skip-browser-warning: true",
]


func _ready() -> void:
	_http_cmd = HTTPRequest.new()
	_http_cmd.timeout = 120.0
	add_child(_http_cmd)

	_http_check = HTTPRequest.new()
	_http_check.timeout = 8.0
	add_child(_http_check)

	_http_reset = HTTPRequest.new()
	_http_reset.timeout = 10.0
	add_child(_http_reset)


func set_server_url(url: String) -> void:
	server_url = url.rstrip("/")


func check_connection() -> void:
	if _http_check.get_http_client_status() != HTTPClient.STATUS_DISCONNECTED:
		_http_check.cancel_request()
	_http_check.request_completed.connect(_on_ping_done, CONNECT_ONE_SHOT)
	_http_check.request(server_url + "/state", HEADERS)


func send_command(command: String) -> void:
	if _http_cmd.get_http_client_status() != HTTPClient.STATUS_DISCONNECTED:
		_http_cmd.cancel_request()
	_http_cmd.request_completed.connect(_on_command_done, CONNECT_ONE_SHOT)
	var body = JSON.stringify({"command": command})
	_http_cmd.request(server_url + "/command", HEADERS, HTTPClient.METHOD_POST, body)


func get_state() -> void:
	_http_check.request_completed.connect(_on_state_done, CONNECT_ONE_SHOT)
	_http_check.request(server_url + "/state", HEADERS)


func reset_game() -> void:
	_http_reset.request_completed.connect(_on_reset_done, CONNECT_ONE_SHOT)
	_http_reset.request(server_url + "/reset", HEADERS, HTTPClient.METHOD_POST, "{}")


# ── Обработчики ───────────────────────────────────────────

func _on_command_done(result: int, code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	if result != HTTPRequest.RESULT_SUCCESS:
		error_occurred.emit("Ошибка соединения (result=%d)" % result)
		return
	if code != 200:
		error_occurred.emit("Сервер вернул %d" % code)
		return
	var text = body.get_string_from_utf8()
	var json = JSON.new()
	if json.parse(text) != OK:
		# Попробуем вытащить хоть что-то
		error_occurred.emit("Ошибка парсинга ответа")
		return
	var data = json.get_data()
	var narrative = str(data.get("response", ""))
	var state = data.get("state", {})
	response_done.emit(narrative, state)


func _on_ping_done(result: int, code: int, _h, _b) -> void:
	connected.emit(result == HTTPRequest.RESULT_SUCCESS and code == 200)


func _on_state_done(result: int, code: int, _h, body: PackedByteArray) -> void:
	if result != HTTPRequest.RESULT_SUCCESS or code != 200:
		return
	var json = JSON.new()
	if json.parse(body.get_string_from_utf8()) == OK:
		state_received.emit(json.get_data())


func _on_reset_done(result: int, code: int, _h, body: PackedByteArray) -> void:
	if result != HTTPRequest.RESULT_SUCCESS or code != 200:
		error_occurred.emit("Ошибка сброса")
		return
	var json = JSON.new()
	if json.parse(body.get_string_from_utf8()) == OK:
		state_received.emit(json.get_data().get("state", {}))
