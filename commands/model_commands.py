"""模型管理命令"""
from typing import Tuple
from src.plugin_system import BaseCommand
from ..sd_client import StableDiffusionClient


class CurrentModelCommand(BaseCommand):
    """查看当前模型命令 - /drawmodel"""

    command_name = "drawmodel"
    command_description = "查看当前使用的 Stable Diffusion 模型"
    command_pattern = r"^/drawmodel$"

    async def execute(self) -> Tuple[bool, str, bool]:
        """执行查看当前模型命令"""
        try:
            api_url = self.get_config("api.base_url", "http://localhost:7860")
            client = StableDiffusionClient(base_url=api_url)

            current_model = await client.get_current_model()

            if current_model:
                await self.send_text(f"📦 当前使用的模型: {current_model}")
                return True, f"当前模型: {current_model}", True
            else:
                await self.send_text("❌ 无法获取当前模型信息")
                return False, "获取模型信息失败", True

        except Exception as e:
            await self.send_text(f"❌ 查询模型时出错: {str(e)}")
            return False, f"执行出错: {str(e)}", True


class SwitchModelCommand(BaseCommand):
    """切换模型命令 - /switchmodel [model_name]"""

    command_name = "switchmodel"
    command_description = "切换 Stable Diffusion 模型（不带参数则列出可用模型）"
    command_pattern = r"^/switchmodel(?:\s+(?P<model_name>.+))?$"

    async def execute(self) -> Tuple[bool, str, bool]:
        """执行切换模型命令"""
        try:
            api_url = self.get_config("api.base_url", "http://localhost:7860")
            client = StableDiffusionClient(base_url=api_url)

            # matched_groups 中键存在但值为 None 时，get 默认值不生效，需要用 or 兜底
            user_input = (self.matched_groups.get("model_name") or "").strip()

            # 始终从 SD API 获取真实模型列表
            api_models = await client.get_models()
            if not api_models:
                await self.send_text("❌ 无法连接 Stable Diffusion API，请检查 SD WebUI 是否正常运行")
                return False, "获取模型列表失败", True

            current_model = await client.get_current_model()

            # 获取配置的可选模型列表（用于过滤显示）
            config_models = self.get_config("generation.available_models", [])

            # 决定显示的模型列表：配置不为空则用它过滤，否则显示全部
            if config_models:
                # 用配置列表过滤 API 返回的模型（模糊匹配 title 和 model_name）
                display_models = []
                for api_m in api_models:
                    title = api_m.get("title", "")
                    model_name = api_m.get("model_name", "")
                    for cm in config_models:
                        if cm in title or cm in model_name or cm == title.split(" [")[0] if " [" in title else False:
                            display_models.append(api_m)
                            break
                if not display_models:
                    # 配置中的模型名与 API 返回的都不匹配，显示全部 API 模型
                    display_models = api_models
                    await self.send_text("⚠️ 配置的 available_models 与 SD 中实际模型未匹配，显示全部模型")
            else:
                display_models = api_models

            # 如果没有提供模型名称，列出可选模型
            if not user_input:
                lines = []
                for m in display_models:
                    title = m.get("title", "未知")
                    is_current = current_model and title == current_model
                    prefix = "👉 " if is_current else "   "
                    lines.append(f"{prefix}{title}")
                models_text = "\n".join(lines)
                current_text = f"\n当前模型: {current_model}" if current_model else ""
                await self.send_text(f"📋 SD 中的可选模型:{current_text}\n\n{models_text}\n\n用法: /switchmodel <模型名>")
                return True, "显示可选模型列表", True

            # 使用 API 的 find_model 匹配用户输入
            matched = await client.find_model(user_input)
            if not matched:
                # 没找到，显示可用模型列表供参考
                lines = [f"  {m.get('title', '未知')}" for m in display_models[:10]]
                models_preview = "\n".join(lines)
                suffix = f"\n  ...还有 {len(display_models) - 10} 个" if len(display_models) > 10 else ""
                await self.send_text(f"❌ 未找到匹配的模型: {user_input}\n\n可用的模型（前10个）:\n{models_preview}{suffix}")
                return False, "模型未找到", True

            matched_title = matched.get("title", user_input)

            # 如果配置了 available_models，检查匹配到的模型是否在配置中
            if config_models:
                found_in_config = False
                for cm in config_models:
                    if cm in matched_title or cm in matched.get("model_name", ""):
                        found_in_config = True
                        break
                if not found_in_config:
                    await self.send_text(
                        f"⚠️ 模型 '{matched_title}' 在 SD 中存在，但不在配置的 available_models 列表中\n"
                        f"仍将为你切换，如需限制可用模型，请在 config.toml 中更新 available_models"
                    )

            await self.send_text(f"🔄 正在切换到模型: {matched_title}...")

            success, error_msg = await client.switch_model(matched_title)

            if success:
                await self.send_text(f"✅ 成功切换到模型: {matched_title}")
                return True, f"切换到模型: {matched_title}", True
            else:
                await self.send_text(f"❌ 切换模型失败: {error_msg if error_msg else '未知错误'}")
                return False, "切换模型失败", True

        except Exception as e:
            await self.send_text(f"❌ 切换模型时出错: {str(e)}")
            return False, f"执行出错: {str(e)}", True
