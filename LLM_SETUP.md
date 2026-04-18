# Подключение различных LLM провайдеров

Теперь вы можете использовать не только Ollama, но и другие LLM через API.

## Быстрый старт

### 1. Ollama (локально)
```json
{
  "llm_provider": "ollama",
  "llm_model": "gemma2:9b"
}
```

### 2. OpenAI API
```json
{
  "llm_provider": "openai",
  "llm_model": "gpt-4o",
  "api_key": "sk-your-api-key-here"
}
```

### 3. Groq (быстрые бесплатные модели)
Зарегистрируйтесь на https://console.groq.com/ и получите API ключ.

```json
{
  "llm_provider": "groq",
  "llm_model": "llama-3.1-70b-versatile",
  "api_key": "gsk_your-api-key-here"
}
```

**Доступные модели Groq:**
- `llama-3.1-70b-versatile` - Llama 3.1 70B
- `llama-3.1-8b-instant` - Llama 3.1 8B
- `mixtral-8x7b-32768` - Mixtral 8x7B
- `gemma2-9b-it` - Gemma 2 9B

### 4. Together AI
Зарегистрируйтесь на https://together.ai/ и получите API ключ.

```json
{
  "llm_provider": "together",
  "llm_model": "meta-llama/Llama-3-70b-chat-hf",
  "api_key": "your-together-api-key"
}
```

**Популярные модели Together AI:**
- `meta-llama/Llama-3-70b-chat-hf` - Llama 3 70B
- `mistralai/Mixtral-8x7B-Instruct-v0.1` - Mixtral 8x7B
- `Qwen/Qwen2.5-72B-Instruct-Turbo` - Qwen 2.5 72B

### 5. Kluster AI
Зарегистрируйтесь на https://kluster.ai/ и получите API ключ.

```json
{
  "llm_provider": "kluster",
  "llm_model": "ваша-модель",
  "api_key": "9ba7398f-80ba-40a2-9dd4-da304de49be5"
}
```

### 6. Кастомный OpenAI-совместимый API
Для LocalAI, vLLM, LM Studio и других совместимых серверов:

```json
{
  "llm_provider": "openai_compatible",
  "llm_model": "ваша-модель",
  "api_key": "любой-ключ-или-пусто",
  "api_url": "http://localhost:8080/v1/chat/completions"
}
```

## Настройка в world.json

Откройте `echo_sim/config/world.json` и добавьте/измените поля:

```json
{
  "epoch": "medieval",
  "narrative_tone": "adventure",
  
  "llm_provider": "groq",
  "llm_model": "llama-3.1-70b-versatile",
  "api_key": "gsk_your-key-here",
  
  "llm_temperature": 0.7,
  "llm_max_tokens": 2048,
  "llm_timeout": 120,
  
  "context_size": 10,
  "server_port": 8080,
  
  ...остальные настройки...
}
```

## Дополнительные параметры

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `llm_provider` | Тип провайдера: `ollama`, `openai`, `groq`, `together`, `kluster`, `localai`, `vllm`, `openai_compatible` | `ollama` |
| `llm_model` | Название модели | `llama3` |
| `api_key` | API ключ (обязательно для облачных провайдеров) | - |
| `api_url` | URL API (для кастомных провайдеров) | зависит от провайдера |
| `llm_temperature` | Температура генерации (0.0-2.0) | `0.7` |
| `llm_max_tokens` | Максимум токенов в ответе | `2048` |
| `llm_timeout` | Таймаут запроса в секундах | `120` |
| `ollama_url` | URL локального Ollama | `http://localhost:11434/api/generate` |

## Примеры конфигураций

### Groq (бесплатно, быстро)
```json
{
  "llm_provider": "groq",
  "llm_model": "llama-3.1-70b-versatile",
  "api_key": "gsk_...",
  "llm_temperature": 0.7
}
```

### OpenAI GPT-4
```json
{
  "llm_provider": "openai",
  "llm_model": "gpt-4o",
  "api_key": "sk-...",
  "llm_temperature": 0.7,
  "llm_max_tokens": 4096
}
```

### Локальный LM Studio
Запустите LM Studio, включите сервер и укажите:
```json
{
  "llm_provider": "openai_compatible",
  "llm_model": "local-model",
  "api_key": "lm-studio",
  "api_url": "http://localhost:1234/v1/chat/completions"
}
```

### vLLM сервер
```json
{
  "llm_provider": "vllm",
  "llm_model": "meta-llama/Llama-2-7b-chat-hf",
  "api_key": "EMPTY",
  "api_url": "http://localhost:8000/v1/chat/completions"
}
```

## Получение API ключей

- **Groq**: https://console.groq.com/keys (бесплатно)
- **OpenAI**: https://platform.openai.com/api-keys (платно)
- **Together AI**: https://api.together.xyz/settings/api-keys (бесплатный триал)
- **Kluster AI**: https://kluster.ai/ (получите ключ в личном кабинете)

## Тестирование подключения

```bash
cd /workspace
python -c "
from echo_sim.core.llm_provider import create_llm_provider
config = {
    'llm_provider': 'groq',
    'llm_model': 'llama-3.1-70b-versatile',
    'api_key': 'gsk_your-key'
}
provider = create_llm_provider(config)
print(f'Provider: {type(provider).__name__}')
"
```
