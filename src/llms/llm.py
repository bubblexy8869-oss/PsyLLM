"""
LLM模块
参考deer-flow的设计，提供统一的LLM访问接口
"""

import os
import yaml
import httpx
import logging
import asyncio
import aiofiles
from pathlib import Path
from typing import Dict, Any, Literal, get_args
from functools import lru_cache

from langchain_openai import ChatOpenAI
# from langchain_deepseek import ChatDeepSeek  # 暂时注释，需要时再启用
from langchain_core.language_models import BaseLanguageModel


logger = logging.getLogger(__name__)

# LLM类型定义
LLMType = Literal["basic", "reasoning", "vision"]

# LLM实例缓存
_llm_cache: Dict[LLMType, BaseLanguageModel] = {}


def _get_config_file_path() -> str:
    """获取配置文件路径"""
    return str((Path(__file__).parent.parent.parent / "config" / "llm_config.yaml").resolve())


def _get_llm_type_config_keys() -> Dict[str, str]:
    """获取LLM类型到配置键的映射"""
    return {
        "basic": "BASIC_MODEL",
        "reasoning": "REASONING_MODEL", 
        "vision": "VISION_MODEL",
    }


def _get_env_llm_conf(llm_type: str) -> Dict[str, Any]:
    """
    从环境变量获取LLM配置
    环境变量格式: {LLM_TYPE}_MODEL__{KEY}
    例如: BASIC_MODEL__api_key, BASIC_MODEL__base_url
    """
    prefix = f"{llm_type.upper()}_MODEL__"
    conf = {}
    for key, value in os.environ.items():
        if key.startswith(prefix):
            conf_key = key[len(prefix):].lower()
            # 类型转换
            if conf_key in ["temperature"]:
                try:
                    conf[conf_key] = float(value)
                except ValueError:
                    conf[conf_key] = value
            elif conf_key in ["max_tokens", "timeout"]:
                try:
                    conf[conf_key] = int(value)
                except ValueError:
                    conf[conf_key] = value
            elif conf_key in ["verify_ssl"]:
                conf[conf_key] = value.lower() in ("true", "1", "yes", "on")
            else:
                conf[conf_key] = value
    return conf


def _load_yaml_config(config_path: str) -> Dict[str, Any]:
    """加载YAML配置文件 - 同步版本（fallback）"""
    try:
        config_file = Path(config_path)
        if not config_file.exists():
            logger.warning(f"Config file not found: {config_path}")
            return {}
        
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}
        
        logger.info(f"Loaded config from: {config_path}")
        return config
    except Exception as e:
        logger.error(f"Failed to load config file {config_path}: {e}")
        return {}


async def _load_yaml_config_async(config_path: str) -> Dict[str, Any]:
    """加载YAML配置文件 - 异步版本"""
    try:
        config_file = Path(config_path)
        if not config_file.exists():
            logger.warning(f"Config file not found: {config_path}")
            return {}
        
        async with aiofiles.open(config_file, 'r', encoding='utf-8') as f:
            content = await f.read()
            config = yaml.safe_load(content) or {}
        
        logger.info(f"Loaded config from: {config_path}")
        return config
    except Exception as e:
        logger.error(f"Failed to load config file {config_path}: {e}")
        return {}


def _create_llm_use_conf(llm_type: LLMType, conf: Dict[str, Any]) -> BaseLanguageModel:
    """使用配置创建LLM实例"""
    llm_type_config_keys = _get_llm_type_config_keys()
    config_key = llm_type_config_keys.get(llm_type)
    
    if not config_key:
        raise ValueError(f"Unknown LLM type: {llm_type}")
    
    llm_conf = conf.get(config_key, {})
    logger.debug(f"Raw config for {llm_type} (key: {config_key}): {llm_conf}")
    
    if not isinstance(llm_conf, dict):
        raise ValueError(f"Invalid LLM configuration for {llm_type}: {llm_conf}")
    
    # 从环境变量获取配置
    env_conf = _get_env_llm_conf(llm_type)
    logger.debug(f"Environment config for {llm_type}: {env_conf}")
    
    # 合并配置，环境变量优先
    merged_conf = {**llm_conf, **env_conf}
    logger.debug(f"Merged config for {llm_type}: {merged_conf}")
    
    if not merged_conf:
        logger.error(f"Configuration details - config_key: {config_key}, yaml_config: {conf.keys()}, llm_conf: {llm_conf}, env_conf: {env_conf}")
        raise ValueError(f"No configuration found for LLM type: {llm_type}")
    
    # 处理推理模型的特殊配置
    if llm_type == "reasoning":
        if "base_url" in merged_conf:
            merged_conf["api_base"] = merged_conf.pop("base_url")
    
    # 处理SSL验证设置
    verify_ssl = merged_conf.pop("verify_ssl", True)
    
    # 如果禁用SSL验证，创建自定义HTTP客户端
    if not verify_ssl:
        http_client = httpx.Client(verify=False)
        http_async_client = httpx.AsyncClient(verify=False)
        merged_conf["http_client"] = http_client
        merged_conf["http_async_client"] = http_async_client
        logger.warning(f"SSL verification disabled for {llm_type} LLM")
    
    try:
        # 根据LLM类型创建不同的实例
        if llm_type == "reasoning" and merged_conf.get("model", "").startswith("deepseek"):
            # 需要时再启用DeepSeek
            # return ChatDeepSeek(**merged_conf)
            logger.warning(f"DeepSeek import is disabled, using ChatOpenAI for {llm_type}")
            return ChatOpenAI(**merged_conf)
        else:
            return ChatOpenAI(**merged_conf)
    except Exception as e:
        logger.error(f"Failed to create {llm_type} LLM: {e}")
        raise


async def get_llm_by_type_async(llm_type: LLMType) -> BaseLanguageModel:
    """
    根据类型获取LLM实例，支持缓存 - 异步版本
    
    Args:
        llm_type: LLM类型
        
    Returns:
        LLM实例
    """
    if llm_type in _llm_cache:
        return _llm_cache[llm_type]
    
    config_path = _get_config_file_path()
    conf = await _load_yaml_config_async(config_path)
    llm = _create_llm_use_conf(llm_type, conf)
    _llm_cache[llm_type] = llm
    
    logger.info(f"Created and cached {llm_type} LLM instance")
    return llm


def get_llm_by_type(llm_type: LLMType) -> BaseLanguageModel:
    """
    根据类型获取LLM实例，支持缓存 - 同步版本（使用异步方式包装）
    
    Args:
        llm_type: LLM类型
        
    Returns:
        LLM实例
    """
    if llm_type in _llm_cache:
        return _llm_cache[llm_type]
    
    # 在LangGraph Studio中，使用asyncio.to_thread来避免阻塞
    try:
        # 检查是否在事件循环中
        loop = asyncio.get_running_loop()
        # 如果在异步环境中，使用线程池执行同步代码
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(_get_llm_sync, llm_type)
            return future.result()
    except RuntimeError:
        # 不在事件循环中，直接执行同步代码
        return _get_llm_sync(llm_type)


def _get_llm_sync(llm_type: LLMType) -> BaseLanguageModel:
    """同步获取LLM实例的内部函数"""
    config_path = _get_config_file_path()
    conf = _load_yaml_config(config_path)
    llm = _create_llm_use_conf(llm_type, conf)
    _llm_cache[llm_type] = llm
    
    logger.info(f"Created and cached {llm_type} LLM instance")
    return llm


def get_configured_llm_models() -> Dict[str, list[str]]:
    """
    获取所有已配置的LLM模型，按类型分组
    
    Returns:
        LLM类型到模型名称列表的映射字典
    """
    try:
        config_path = _get_config_file_path()
        conf = _load_yaml_config(config_path)
        llm_type_config_keys = _get_llm_type_config_keys()
        
        configured_models: Dict[str, list[str]] = {}
        
        for llm_type in get_args(LLMType):
            # 从YAML文件获取配置
            config_key = llm_type_config_keys.get(llm_type, "")
            yaml_conf = conf.get(config_key, {}) if config_key else {}
            
            # 从环境变量获取配置
            env_conf = _get_env_llm_conf(llm_type)
            
            # 合并配置，环境变量优先
            merged_conf = {**yaml_conf, **env_conf}
            
            # 检查是否配置了模型
            model_name = merged_conf.get("model")
            if model_name:
                configured_models.setdefault(llm_type, []).append(model_name)
        
        return configured_models
    
    except Exception as e:
        logger.error(f"Failed to load LLM configuration: {e}")
        return {}


# 代理到LLM类型的映射（参考deer-flow）
AGENT_LLM_MAP: Dict[str, LLMType] = {
    "intent_understanding": "basic",
    "response_generation": "basic",
    "task_decomposition": "reasoning",
    "workflow_planning": "reasoning",
    "command_execution": "basic",
    "knowledge_qa": "basic",
    "monitoring": "basic",
    "aggregation": "basic",
}


def get_llm_for_agent(agent_name: str) -> BaseLanguageModel:
    """
    根据代理名称获取对应的LLM实例
    
    Args:
        agent_name: 代理名称
        
    Returns:
        LLM实例
    """
    llm_type = AGENT_LLM_MAP.get(agent_name, "basic")
    return get_llm_by_type(llm_type)


# 便捷函数
def get_basic_llm() -> BaseLanguageModel:
    """获取基础LLM实例"""
    return get_llm_by_type("basic")


def get_reasoning_llm() -> BaseLanguageModel:
    """获取推理LLM实例"""
    return get_llm_by_type("reasoning")


def get_vision_llm() -> BaseLanguageModel:
    """获取视觉LLM实例"""
    return get_llm_by_type("vision")


@lru_cache(maxsize=1)
def get_llm_health_status() -> Dict[str, Any]:
    """
    获取LLM健康状态
    
    Returns:
        健康状态信息
    """
    try:
        configured_models = get_configured_llm_models()
        total_models = sum(len(models) for models in configured_models.values())
        
        return {
            "status": "healthy" if total_models > 0 else "no_models_configured",
            "configured_models": configured_models,
            "total_models": total_models,
            "cache_size": len(_llm_cache),
            "available_types": list(get_args(LLMType))
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "configured_models": {},
            "total_models": 0,
            "cache_size": len(_llm_cache),
            "available_types": list(get_args(LLMType))
        }