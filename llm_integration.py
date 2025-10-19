import asyncio
import json
from typing import Dict, Tuple
from agent_framework.config import Config

class TokenAccountant:
    """Design Pattern: Theo dõi và tính toán chi phí token cho các model LLM."""
    def __init__(self):
        # Cấu trúc: { 'model_name': {'input': X, 'output': Y, 'calls': Z, 'cost_per_mil_input': A, 'cost_per_mil_output': B} }
        self.usage_stats: Dict[str, Dict] = {}
        self._model_costs = {
            "gpt-4-turbo-preview": {"cost_per_mil_input": 10.00, "cost_per_mil_output": 30.00},
            "default": {"cost_per_mil_input": 1.00, "cost_per_mil_output": 3.00}
        }

    def log_usage(self, model_name: str, input_tokens: int, output_tokens: int):
        if model_name not in self.usage_stats:
            costs = self._model_costs.get(model_name, self._model_costs["default"])
            self.usage_stats[model_name] = {
                "input_tokens": 0, "output_tokens": 0, "calls": 0, **costs
            }
        
        self.usage_stats[model_name]["input_tokens"] += input_tokens
        self.usage_stats[model_name]["output_tokens"] += output_tokens
        self.usage_stats[model_name]["calls"] += 1
        print(f"[TokenAccountant] 🪙 Logged: {model_name} - Input: {input_tokens}, Output: {output_tokens}")

    def get_summary(self) -> str:
        summary = "\n--- LLM Token Usage & Cost Summary ---\n"
        total_cost = 0.0
        for model, stats in self.usage_stats.items():
            input_cost = (stats["input_tokens"] / 1_000_000) * stats["cost_per_mil_input"]
            output_cost = (stats["output_tokens"] / 1_000_000) * stats["cost_per_mil_output"]
            model_total_cost = input_cost + output_cost
            total_cost += model_total_cost
            summary += (
                f"- Model: {model}\n"
                f"  - Calls: {stats['calls']}\n"
                f"  - Tokens: {stats['input_tokens']} (input) + {stats['output_tokens']} (output) = {stats['input_tokens'] + stats['output_tokens']} (total)\n"
                f"  - Estimated Cost: ${model_total_cost:.4f}\n"
            )
        summary += f"\n**Total Estimated Cost: ${total_cost:.4f}**\n"
        summary += "--------------------------------------\n"
        return summary

class LLMClient:
    """Một client để tương tác với LLM, tích hợp sẵn TokenAccountant."""
    def __init__(self, config: Config, accountant: TokenAccountant):
        self.config = config
        self.accountant = accountant

    async def call(self, provider: str, model_config_name: str, prompt: str) -> str:
        """Mô phỏng việc gọi API LLM và ghi lại lượng token sử dụng."""
        try:
            model_config = self.config.providers[provider].models[model_config_name]
        except KeyError:
            raise ValueError(f"Config for '{model_config_name}' not found.")

        print(f"[LLMClient] 📞 Calling model '{model_config.model_name}' for '{model_config_name}' task...")
        await asyncio.sleep(1) # Giả lập độ trễ mạng

        # --- PHẦN MÔ PHỎNG API RESPONSE ---
        # Trong thực tế, bạn sẽ gọi API ở đây và nhận response thật
        # Ví dụ: response = openai.ChatCompletion.create(...)
        # simulated_text_response = response.choices[0].message.content
        # usage = response.usage
        # input_tokens = usage.prompt_tokens
        # output_tokens = usage.completion_tokens

        # Mô phỏng response cho task "planner"
        if model_config_name == "planner":
            simulated_text_response = json.dumps([
                {"id": "A1.1", "description": "Tạo Dockerfile cho ứng dụng", "assigned_to": "DevOps", "dependencies": []},
                {"id": "A1.2", "description": "Tạo file docker-compose cho các services", "assigned_to": "DevOps", "dependencies": ["A1.1"]}
            ])
            input_tokens = len(prompt.split()) + len(model_config.system_prompt.split()) # Ước tính
            output_tokens = len(simulated_text_response.split())
        else:
            simulated_text_response = "# Some generated code here..."
            input_tokens = len(prompt.split()) + len(model_config.system_prompt.split())
            output_tokens = 500
        # --- KẾT THÚC PHẦN MÔ PHỎNG ---

        # Ghi lại lượng token đã sử dụng
        self.accountant.log_usage(model_config.model_name, input_tokens, output_tokens)

        return simulated_text_response
