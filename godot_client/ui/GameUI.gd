## GameUI.gd — главный контроллер интерфейса Echo-Sim
extends Control

@onready var narrative_log: RichTextLabel = $Layout/Left/NarrativeScroll/NarrativeLog
@onready var input_field: LineEdit = $Layout/Left/InputRow/InputField
@onready var send_btn: Button = $Layout/Left/InputRow/SendBtn
@onready var hp_bar: ProgressBar = $Layout/Right/StatusPanel/HPRow/HPBar
@onready var hp_label: Label = $Layout/Right/StatusPanel/HPRow/HPLabel
@onready var location_label: Label = $Layout/Right/StatusPanel/LocationLabel
@onready var time_label: Label = $Layout/Right/StatusPanel/TimeLabel
@onready var gold_label: Label = $Layout/Right/StatusPanel/GoldLabel
@onready var skills_label: RichTextLabel = $Layout/Right/StatusPanel/SkillsLabel
@onready var npcs_label: RichTextLabel = $Layout/Right/StatusPanel/NPCsLabel
@onready var quests_label: RichTextLabel = $Layout/Right/StatusPanel/QuestsLabel
@onready var journal_label: RichTextLabel = $Layout/Right/StatusPanel/JournalLabel
@onready var loading_label: Label = $Layout/Left/LoadingLabel
@onready var location_image: TextureRect = $Layout/Left/LocationImage
@onready var api: Node = $GameAPI

# Кэш текстур локаций
var _location_textures: Dictionary = {}
var _cmd_history: Array = []
var _history_idx: int = -1
var _busy: bool = false
var _retry_count: int = 0
const MAX_RETRIES = 8
const SERVER_URL = "https://shout-clutter-detonator.ngrok-free.dev"
const FALLBACK_URL = "http://127.0.0.1:8080"


func _ready() -> void:
	api.response_done.connect(_on_response_done)
	api.state_received.connect(_on_state)
	api.error_occurred.connect(_on_error)
	api.connected.connect(_on_connected)
	send_btn.pressed.connect(_on_send)
	input_field.text_submitted.connect(_on_send)
	input_field.editable = false
	send_btn.disabled = true
	_start_server_if_local()
	var saved_url = _load_server_url()
	api.set_server_url(saved_url)
	await get_tree().create_timer(1.5).timeout
	_try_connect()


func _start_server_if_local() -> void:
	# Автозапуск только если подключаемся локально
	var url = _load_server_url()
	if "127.0.0.1" not in url and "localhost" not in url and "192.168." not in url:
		return  # ngrok или внешний адрес — сервер уже запущен на ПК
	# Ищем python рядом с проектом
	var server_script = ProjectSettings.globalize_path("res://../echo_sim/server.py")
	if not FileAccess.file_exists(server_script):
		return
	var pid = OS.create_process("python", [server_script])
	if pid > 0:
		_append_system("[color=#6a5a30]⚙ Сервер запускается...[/color]")


func _load_server_url() -> String:
	var f = FileAccess.open("user://server_url.txt", FileAccess.READ)
	if f:
		var url = f.get_line().strip_edges()
		f.close()
		if url.begins_with("http"):
			return url
	return SERVER_URL


func _save_server_url(url: String) -> void:
	var f = FileAccess.open("user://server_url.txt", FileAccess.WRITE)
	if f:
		f.store_line(url)
		f.close()


func _try_connect() -> void:
	_append_system("⟳ Подключение... (попытка %d/%d)" % [_retry_count + 1, MAX_RETRIES])
	api.check_connection()


func _on_connected(ok: bool) -> void:
	if ok:
		_retry_count = 0
		input_field.editable = true
		send_btn.disabled = false
		input_field.grab_focus()
		_append_system("✓ Подключено к %s" % api.server_url)
		_set_busy(true)
		api.send_command("осмотреться")
	else:
		_retry_count += 1
		if _retry_count < MAX_RETRIES:
			_append_system("[color=#8b4513]Нет ответа, повтор через 3 сек...[/color]")
			await get_tree().create_timer(3.0).timeout
			_try_connect()
		else:
			_append_system("[color=#cc3333]Не удалось подключиться.[/color]")
			_append_system("[color=#7a6a40]Введи адрес сервера (например ngrok URL) и нажми →[/color]")
			input_field.editable = true
			input_field.text = api.server_url
			send_btn.disabled = false
			send_btn.text = "⟳"
			send_btn.pressed.disconnect(_on_send)
			send_btn.pressed.connect(_on_url_submit)
			input_field.text_submitted.disconnect(_on_send)
			input_field.text_submitted.connect(_on_url_submit)


func _on_url_submit(_text: String = "") -> void:
	var url = input_field.text.strip_edges()
	if not url.begins_with("http"):
		url = "http://" + url
	_save_server_url(url)
	api.set_server_url(url)
	input_field.text = ""
	input_field.placeholder_text = "▶  что делаешь?"
	send_btn.text = "→"
	send_btn.pressed.disconnect(_on_url_submit)
	send_btn.pressed.connect(_on_send)
	input_field.text_submitted.disconnect(_on_url_submit)
	input_field.text_submitted.connect(_on_send)
	input_field.editable = false
	send_btn.disabled = true
	_retry_count = 0
	_try_connect()


func _on_reconnect() -> void:
	send_btn.text = "→"
	send_btn.disabled = true
	send_btn.pressed.disconnect(_on_reconnect)
	send_btn.pressed.connect(_on_send)
	_retry_count = 0
	_try_connect()


func _input(event: InputEvent) -> void:
	if not input_field.has_focus() or not event is InputEventKey or not event.pressed:
		return
	if event.keycode == KEY_UP and _cmd_history.size() > 0:
		_history_idx = max(0, (_cmd_history.size() - 1) if _history_idx == -1 else _history_idx - 1)
		input_field.text = _cmd_history[_history_idx]
		input_field.caret_column = input_field.text.length()
	elif event.keycode == KEY_DOWN:
		if _history_idx == -1:
			return
		_history_idx += 1
		if _history_idx >= _cmd_history.size():
			_history_idx = -1
			input_field.text = ""
		else:
			input_field.text = _cmd_history[_history_idx]
			input_field.caret_column = input_field.text.length()


func _on_send(_text: String = "") -> void:
	if _busy:
		return
	var cmd = input_field.text.strip_edges()
	if cmd.is_empty():
		return
	if _cmd_history.is_empty() or _cmd_history[-1] != cmd:
		_cmd_history.append(cmd)
	_history_idx = -1
	input_field.text = ""
	_append_player(cmd)
	_set_busy(true)
	api.send_command(cmd)


# ── Ответы сервера ────────────────────────────────────────

func _on_response_done(narrative: String, state: Dictionary) -> void:
	_set_busy(false)
	loading_label.text = ""

	if narrative.strip_edges() != "":
		_append_narrative(narrative)

	_append_separator()

	if not state.is_empty():
		_update_status(state)

	input_field.grab_focus()


func _on_state(state: Dictionary) -> void:
	_update_status(state)


func _on_error(message: String) -> void:
	_set_busy(false)
	loading_label.text = ""
	_append_system("[color=#cc3333]⚠ %s[/color]" % message)


# ── Нарратив ──────────────────────────────────────────────

func _append_narrative(text: String) -> void:
	narrative_log.append_text("\n[color=#d4c9a8]%s[/color]" % text)
	_scroll_to_bottom()


func _append_player(cmd: String) -> void:
	narrative_log.append_text("\n\n[color=#e8c84a][b]▶  %s[/b][/color]" % cmd)


func _append_system(text: String) -> void:
	narrative_log.append_text("\n[color=#6a5a30][i]%s[/i][/color]" % text)


func _append_separator() -> void:
	narrative_log.append_text(
		"\n[color=#2a2010]%s[/color]" % "·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·"
	)


func _scroll_to_bottom() -> void:
	await get_tree().process_frame
	var scroll = $Layout/Left/NarrativeScroll
	scroll.scroll_vertical = scroll.get_v_scroll_bar().max_value


# ── Статус ────────────────────────────────────────────────

func _update_status(state: Dictionary) -> void:
	var player = state.get("player", {})
	var world  = state.get("world",  {})
	var npcs_all = state.get("npcs", {})

	# HP
	var hp     = int(player.get("health", 0))
	var max_hp = int(player.get("max_health", 100))
	hp_bar.max_value = max_hp
	hp_bar.value = hp
	var pct = float(hp) / float(max_hp) if max_hp > 0 else 0.0
	if pct < 0.3:
		hp_bar.modulate = Color(0.8, 0.2, 0.2)
	elif pct < 0.6:
		hp_bar.modulate = Color(0.85, 0.65, 0.1)
	else:
		hp_bar.modulate = Color(0.3, 0.75, 0.3)
	hp_label.text = "%d / %d" % [hp, max_hp]

	# Локация и время
	var loc_id = world.get("current_location_id", "")
	var locations = world.get("locations", {})
	var loc_data = locations.get(loc_id, {}) if locations.has(loc_id) else {}
	location_label.text = loc_data.get("name", loc_id)
	time_label.text = world.get("game_time_formatted", "00:00")

	# Золото
	var gold = 0
	for item in player.get("inventory", []):
		if str(item).begins_with("кошель с монетами"):
			var parts = str(item).split("(")
			if parts.size() > 1:
				gold = int(parts[1].rstrip(")"))
	gold_label.text = "⚙ %d зол." % gold

	# Навыки
	var skills_text = ""
	var skills = player.get("skills", {})
	for sname in skills:
		var val = int(skills[sname])
		if val > 0:
			var filled = int(float(val) / 100.0 * 6)
			var bar = "█".repeat(filled) + "░".repeat(6 - filled)
			skills_text += "[color=#b8a880]%-10s[/color] [color=#4a3a18]%s[/color] [color=#e8c84a]%d[/color]\n" % [sname, bar, val]
	skills_label.text = skills_text.strip_edges()

	# NPC в локации
	var npcs_here = []
	for npc_id in npcs_all:
		var npc = npcs_all[npc_id]
		if npc.get("location_id") == loc_id and npc.get("status") == "alive":
			npcs_here.append("· " + str(npc.get("name", npc_id)))
	npcs_label.text = "\n".join(npcs_here) if npcs_here.size() > 0 else "[color=#4a3a18]никого[/color]"

	# Квесты
	var q_lines = []
	for q in player.get("active_quests", []):
		var qst = str(q.get("status", "???")).substr(0, 3).to_upper()
		q_lines.append("[color=#6a5a30][%s][/color] %s" % [qst, str(q.get("title", "?"))])
	quests_label.text = "\n".join(q_lines) if q_lines.size() > 0 else "[color=#4a3a18]нет[/color]"

	# Журнал — последние 4 записи
	var journal = player.get("journal", [])
	var j_lines = []
	var j_start = max(0, journal.size() - 4)
	for i in range(j_start, journal.size()):
		var entry = journal[i]
		var mark = "★ " if entry.get("important", false) else "· "
		j_lines.append("[color=#6a5a30]%s%s[/color]" % [mark, str(entry.get("text", "")).substr(0, 50)])
	journal_label.text = "\n".join(j_lines) if j_lines.size() > 0 else "[color=#4a3a18]пусто[/color]"

	# Изображение локации
	_load_location_image(loc_id)


func _load_location_image(loc_id: String) -> void:
	if _location_textures.has(loc_id):
		location_image.texture = _location_textures[loc_id]
		return
	var path = "res://assets/locations/%s.svg" % loc_id
	if not ResourceLoader.exists(path):
		path = "res://assets/locations/default.svg"
	if ResourceLoader.exists(path):
		var tex = load(path)
		if tex:
			_location_textures[loc_id] = tex
			location_image.texture = tex


func _set_busy(busy: bool) -> void:
	_busy = busy
	send_btn.disabled = busy
	input_field.editable = not busy
	if busy:
		loading_label.text = "⏳ GM думает..."
	else:
		loading_label.text = ""
