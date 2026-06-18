"""
VLLM Search Agent Implementation
Local VLLM server-based search agent using OpenAI compatible API
"""

import time
from typing import List, Dict, Optional, Any
from openai import OpenAI
from loguru import logger
import random

from .base_agent import BaseSearchAgent


class VLLMSearchAgent(BaseSearchAgent):
    """
    Search agent implementation using local VLLM server.
    
    This agent connects to a local VLLM server that provides an OpenAI-compatible
    API interface for running open-source language models.
    """
    
    def __init__(self,
                 server_ip: str = "localhost",
                 server_port: int | list[int] = 8000,
                 model_name: str = "your-model-name",
                 api_key: str = "EMPTY",
                 max_retries: int = 10,
                 retry_delay: float = 3.0,
                 **kwargs):
        """
        Initialize VLLM search agent.
        
        Args:
            server_ip: VLLM server IP address
            server_port: VLLM server port (can be int or list of ints for load balancing)
            model_name: Model name to use
            api_key: API key (usually "EMPTY" for local servers)
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            **kwargs: Additional arguments passed to base class
        """
        super().__init__(**kwargs)

        if isinstance(server_port, int):
            server_port_list = [server_port]
        else:
            server_port_list = server_port
        
        self.server_ip = server_ip
        self.server_port_list = server_port_list
        self.model_name = model_name
        self.api_key = api_key
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Initialize OpenAI client for VLLM server
        self.client_list = [OpenAI(
            api_key=api_key,
            base_url=f"http://{server_ip}:{server_port}/v1"
        ) for server_port in server_port_list]
        
        logger.info(f"Initialized VLLM search agent: {server_ip}:{server_port_list}/{model_name}")
    
    def _call_model(self, messages: List[Dict], **kwargs) -> str:
        """
        Call VLLM model.
        
        Args:
            messages: List of conversation messages
            **kwargs: Additional model parameters
            
        Returns:
            Model response as string
        """
        random_client = random.choice(self.client_list)
        
        for attempt in range(self.max_retries):
            try:
                response = random_client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=self.temperature,
                    stop=["</tool_call>", "</answer>"],
                    **kwargs
                )
                
                return response.choices[0].message.content
                
            except Exception as e:
                logger.warning(f"VLLM call attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    import traceback
                    traceback.print_exc()
                    return "Failed to call model."
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get model information.
        
        Returns:
            Dictionary containing model information
        """
        return {
            "type": "vllm",
            "server_ip": self.server_ip,
            "server_port_list": self.server_port_list,
            "model": self.model_name,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay
        }
    
    def health_check(self) -> bool:
        """
        Check if VLLM server is healthy.
        
        Returns:
            True if server is healthy, False otherwise
        """
        try:
            # Simple test call
            test_messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello"}
            ]
            
            response = self._call_model(test_messages)
            return response is not None and not response.startswith("Error:")
            
        except Exception as e:
            logger.error(f"VLLM health check failed: {e}")
            return False
    
    def get_server_status(self) -> Dict[str, Any]:
        """
        Get detailed server status information.
        
        Returns:
            Dictionary containing server status
        """
        try:
            # Test server connectivity
            test_messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Test"}
            ]
            
            response = self._call_model(test_messages)
            
            return {
                "status": "healthy" if response and not response.startswith("Error:") else "unhealthy",
                "server_ip": self.server_ip,
                "server_port_list": self.server_port_list,
                "model": self.model_name,
                "response_preview": response[:100] if response else "No response"
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "server_ip": self.server_ip,
                "server_port_list": self.server_port_list,
                "model": self.model_name,
                "error": str(e)
            }
    
    def switch_model(self, new_model_name: str) -> bool:
        """
        Switch to a different model.
        
        Args:
            new_model_name: Name of the new model to use
            
        Returns:
            True if switch was successful, False otherwise
        """
        try:
            # Test if the new model is available
            test_messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Test"}
            ]
            
            # Temporarily switch model for testing
            old_model = self.model_name
            self.model_name = new_model_name
            
            response = self._call_model(test_messages)
            
            if response and not response.startswith("Error:"):
                logger.info(f"Successfully switched to model: {new_model_name}")
                return True
            else:
                # Revert on failure
                self.model_name = old_model
                logger.error(f"Model {new_model_name} failed test")
                return False
                
        except Exception as e:
            # Revert on failure
            self.model_name = old_model
            logger.error(f"Failed to switch to model {new_model_name}: {e}")
            return False

