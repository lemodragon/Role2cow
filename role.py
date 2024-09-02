# encoding:utf-8

import json
import os
import requests
from requests.exceptions import RequestException

import plugins
from bridge.bridge import Bridge
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common import const
from common.log import logger
from config import conf
from plugins import *

class CloudAssistant:
    def __init__(self):
        config = self._load_config()
        self.api_url = config.get("api_url", "https://your-default-api-url.com/v1/chat/completions")
        self.api_key = config.get("api_key", "your-default-api-key")
        self.model = config.get("model", "THUDM/glm-4-9b-chat")
        self.sessions = {}
        logger.info(f"[CloudAssistant] Initialized with URL: {self.api_url}, Model: {self.model}")

    def _load_config(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(current_dir, "config.json")
        try:
            with open(config_path, 'r') as config_file:
                config = json.load(config_file)
                return config.get("cloud_assistant", {})
        except FileNotFoundError:
            logger.error(f"Config file not found: {config_path}")
            return {}
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in config file: {config_path}")
            return {}

    def get_response(self, session_id, prompt):
        if session_id not in self.sessions:
            self.sessions[session_id] = []

        self.sessions[session_id].append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model,
            "messages": self.sessions[session_id],
            "max_tokens": 1000
        }
        try:
            logger.info(f"[CloudAssistant] Sending request to {self.api_url}")
            response = requests.post(self.api_url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            self.sessions[session_id].append({"role": "assistant", "content": content})
            return content
        except RequestException as e:
            logger.error(f"[CloudAssistant] API request failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"[CloudAssistant] Response status code: {e.response.status_code}")
                logger.error(f"[CloudAssistant] Response content: {e.response.text}")
            raise

    def reset_session(self, session_id):
        if session_id in self.sessions:
            del self.sessions[session_id]

class RolePlay:
    def __init__(self, bot, sessionid, desc, wrapper=None, use_cloud_assistant=False, cloud_assistant=None):
        self.bot = bot
        self.sessionid = sessionid
        self.wrapper = wrapper or "%s"
        self.desc = desc
        self.use_cloud_assistant = use_cloud_assistant
        self.cloud_assistant = cloud_assistant
        self.reset()

    def reset(self):
        if self.use_cloud_assistant:
            self.cloud_assistant.reset_session(self.sessionid)
            self.cloud_assistant.get_response(self.sessionid, self.desc)
        else:
            self.bot.sessions.clear_session(self.sessionid)
            self.bot.sessions.build_session(self.sessionid, system_prompt=self.desc)

    def action(self, user_action):
        if self.use_cloud_assistant:
            try:
                return self.cloud_assistant.get_response(self.sessionid, self.wrapper % user_action)
            except Exception as e:
                logger.error(f"[CloudAssistant] Error: {str(e)}")
                return f"抱歉，我在处理您的请求时遇到了问题。错误信息：{str(e)}"
        else:
            return None  # 返回 None，表示需要使用默认的 ChatGPT 处理

@plugins.register(
    name="Role",
    desc="为你的Bot设置预设角色",
    version="1.8",
    author="lanvent",
)
class Role(Plugin):
    def __init__(self):
        super().__init__()
        curdir = os.path.dirname(__file__)
        config_path = os.path.join(curdir, "roles.json")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                self.tags = {tag: (desc, []) for tag, desc in config["tags"].items()}
                self.roles = {}
                for role in config["roles"]:
                    self.roles[role["title"].lower()] = role
                    for tag in role["tags"]:
                        if tag not in self.tags:
                            logger.warning(f"[Role] unknown tag {tag} ")
                            self.tags[tag] = (tag, [])
                        self.tags[tag][1].append(role)
                for tag in list(self.tags.keys()):
                    if len(self.tags[tag][1]) == 0:
                        logger.debug(f"[Role] no role found for tag {tag} ")
                        del self.tags[tag]

            if len(self.roles) == 0:
                raise Exception("no role found")
            self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
            self.roleplays = {}
            logger.info("[Role] inited")
        except Exception as e:
            if isinstance(e, FileNotFoundError):
                logger.warn(f"[Role] init failed, {config_path} not found, ignore or see https://github.com/zhayujie/chatgpt-on-wechat/tree/master/plugins/role .")
            else:
                logger.warn("[Role] init failed, ignore or see https://github.com/zhayujie/chatgpt-on-wechat/tree/master/plugins/role .")
            raise e
        
        self.cloud_assistant = CloudAssistant()

    def get_role(self, name, find_closest=True, min_sim=0.35):
        name = name.lower()
        found_role = None
        if name in self.roles:
            found_role = name
        elif find_closest:
            import difflib

            def str_simularity(a, b):
                return difflib.SequenceMatcher(None, a, b).ratio()

            max_sim = min_sim
            max_role = None
            for role in self.roles:
                sim = str_simularity(name, role)
                if sim >= max_sim:
                    max_sim = sim
                    max_role = role
            found_role = max_role
        return found_role

    def on_handle_context(self, e_context: EventContext):
        if e_context["context"].type != ContextType.TEXT:
            return
        content = e_context["context"].content
        clist = e_context["context"].content.split(maxsplit=1)
        sessionid = e_context["context"]["session_id"]
        trigger_prefix = conf().get("plugin_trigger_prefix", "$")
        
        if clist[0] == f"{trigger_prefix}停止扮演":
            if sessionid in self.roleplays:
                self.roleplays[sessionid].reset()
                del self.roleplays[sessionid]
                self.reset_chat_settings(sessionid)  # 重置ChatGPT设置
                reply = Reply(ReplyType.INFO, "角色扮演结束!")
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS
            else:
                reply = Reply(ReplyType.INFO, "当前没有进行中的角色扮演。")
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS
            return
        
        if clist[0] == f"{trigger_prefix}角色列表":
            role_list = self.get_role_list()
            reply = Reply(ReplyType.INFO, role_list)
            e_context["reply"] = reply
            e_context.action = EventAction.BREAK_PASS
            return
        
        if sessionid in self.roleplays:
            roleplay = self.roleplays[sessionid]
            if roleplay.use_cloud_assistant:
                try:
                    response = roleplay.action(content)
                    reply = Reply(ReplyType.TEXT, response)
                    e_context["reply"] = reply
                    e_context.action = EventAction.BREAK_PASS
                except Exception as e:
                    logger.error(f"[CloudAssistant] Error: {str(e)}")
                    reply = Reply(ReplyType.ERROR, f"处理请求时发生错误：{str(e)}")
                    e_context["reply"] = reply
                    e_context.action = EventAction.BREAK_PASS
            else:
                prompt = roleplay.action(content)
                if prompt is not None:
                    e_context["context"].type = ContextType.TEXT
                    e_context["context"].content = prompt
                    e_context.action = EventAction.BREAK
            return
        
        if clist[0] == f"{trigger_prefix}角色":
            if len(clist) == 1 or clist[1].lower() in ["help", "帮助"]:
                reply = Reply(ReplyType.INFO, self.get_help_text(verbose=True))
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS
                return
            
            role = self.get_role(clist[1])
            if role is None:
                reply = Reply(ReplyType.ERROR, "角色不存在")
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS
                return
            
            use_cloud_assistant = role.lower() == "数字人-云"
            self.roleplays[sessionid] = RolePlay(
                Bridge().get_bot("chat"),
                sessionid,
                self.roles[role]["descn"],
                self.roles[role].get("wrapper", "%s"),
                use_cloud_assistant,
                self.cloud_assistant if use_cloud_assistant else None
            )
            reply = Reply(ReplyType.INFO, f"预设角色为 {role}:\n" + self.roles[role]["descn"])
            e_context["reply"] = reply
            e_context.action = EventAction.BREAK_PASS
        elif clist[0] == f"{trigger_prefix}设定扮演":
            if len(clist) < 2:
                reply = Reply(ReplyType.ERROR, "请提供角色设定")
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS
                return
            
            self.roleplays[sessionid] = RolePlay(Bridge().get_bot("chat"), sessionid, clist[1], "%s")
            reply = Reply(ReplyType.INFO, f"角色设定为:\n{clist[1]}")
            e_context["reply"] = reply
            e_context.action = EventAction.BREAK_PASS

    def reset_chat_settings(self, sessionid):
        bot = Bridge().get_bot("chat")
        bot.sessions.clear_session(sessionid)
        # 重置为默认的system prompt，如果有的话
        default_system_prompt = conf().get("character_desc", "")
        bot.sessions.build_session(sessionid, system_prompt=default_system_prompt)

    def get_role_list(self):
        role_list = "可用的角色列表：\n\n"
        for role, info in self.roles.items():
            role_list += f"- {info['title']}: {info['remark']}\n"
        return role_list

    def get_help_text(self, verbose=False, **kwargs):
        help_text = "让机器人扮演不同的角色。\n"
        if not verbose:
            return help_text
        trigger_prefix = conf().get("plugin_trigger_prefix", "$")
        help_text = f"使用方法:\n{trigger_prefix}角色列表: 显示所有可用的角色。\n"
        help_text += f"{trigger_prefix}角色" + " 预设角色名: 设定角色为{预设角色名}。\n"
        help_text += f"{trigger_prefix}设定扮演" + " 角色设定: 设定自定义角色人设为{角色设定}。\n"
        help_text += f"{trigger_prefix}停止扮演: 清除设定的角色。\n"
        help_text += "\n目前的角色类型有: \n"
        help_text += "，".join([self.tags[tag][0] for tag in self.tags]) + "。\n"
        help_text += f"\n命令例子: \n{trigger_prefix}角色列表\n"
        help_text += f"{trigger_prefix}角色 数字人-云\n"
        help_text += f"{trigger_prefix}停止扮演\n"
        return help_text
