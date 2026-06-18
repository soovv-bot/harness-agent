"""
VLLM Server Launcher
Launches VLLM server for local model inference with multi-node support
"""

import os
import subprocess
import argparse
import time
import signal
import sys
from typing import List, Optional
from loguru import logger


def launch_single_vllm_server(
    model_path: str,
    model_name: str,
    port: int = 8010,
    tensor_parallel_size: int = 1,
    gpu_memory_utilization: float = 0.8,
    max_model_len: int = 131072,
    dtype: str = "auto",
    gpu_ids: Optional[List[int]] = None,
    **kwargs
):
    """
    Launch a single VLLM server instance.
    
    Args:
        model_path: Path to the model
        model_name: Model name to serve
        port: Server port
        tensor_parallel_size: Number of GPUs to use
        gpu_memory_utilization: GPU memory utilization ratio
        max_model_len: Maximum model length
        dtype: Data type for model
        gpu_ids: Specific GPU IDs to use (if None, uses tensor_parallel_size GPUs)
        **kwargs: Additional VLLM arguments
    """
    gpu_id_str = ",".join(map(str, gpu_ids)) if gpu_ids else None

    rope_scaling = kwargs.get("rope_scaling")
    if not rope_scaling:
        rope_scaling = '\'{"rope_type": "yarn", "factor": 4.0, "original_max_position_embeddings": 32768}\''
    
    # Build VLLM command
    cmd = [
        "vllm", "serve", model_path,
        "--served-model-name", model_name,
        "--port", str(port),
        "--tensor-parallel-size", str(tensor_parallel_size),
        "--gpu-memory-utilization", str(gpu_memory_utilization),
        "--max-model-len", str(max_model_len),
        "--dtype", dtype,
        "--enforce-eager",
        "--rope-scaling", rope_scaling,
    ]
    
    cmd_str = " ".join(cmd)
    
    if gpu_id_str:
        full_command = f"export VLLM_ALLOW_LONG_MAX_MODEL_LEN=1; CUDA_VISIBLE_DEVICES={gpu_id_str} {cmd_str}"
    else:
        full_command = f"export VLLM_ALLOW_LONG_MAX_MODEL_LEN=1; {cmd_str}"

    logger.info(f"Launching VLLM server on port {port} with GPUs: {gpu_ids or f'auto-{tensor_parallel_size}'}")
    logger.debug(f"Command: {full_command}")
    
    process = subprocess.Popen(full_command, shell=True, stdout=None, stderr=None)

    return process


def main():
    parser = argparse.ArgumentParser(description="Launch VLLM server(s)")
    parser.add_argument("--model_path", type=str, required=True, help="Path to the model")
    parser.add_argument("--model_name", type=str, required=True, help="Model name to serve")
    parser.add_argument("--start_port", type=int, default=8010, help="Starting port number")
    parser.add_argument("--num_instances", type=int, default=1, help="Number of server instances")
    parser.add_argument("--tensor_parallel_size", type=int, default=1, help="Tensor parallel size per instance")
    parser.add_argument("--total_gpus", type=int, default=None, help="Total number of GPUs available")
    parser.add_argument("--gpu_memory_utilization", type=float, default=0.8, help="GPU memory utilization")
    parser.add_argument("--max_model_len", type=int, default=131072, help="Maximum model length")
    parser.add_argument("--dtype", type=str, default="auto", help="Data type")
    parser.add_argument("--rope_scaling", type=str, default=None, help="Rope scaling configuration (JSON string)")
    
    args = parser.parse_args()
    
    # Calculate GPU allocation if total_gpus is specified
    if args.total_gpus:
        if args.total_gpus % args.tensor_parallel_size != 0:
            raise ValueError("Total GPUs must be divisible by tensor parallel size")
        instance_num = args.total_gpus // args.tensor_parallel_size
        if args.num_instances > instance_num:
            logger.warning(f"Requested {args.num_instances} instances but only {instance_num} can be created with {args.total_gpus} GPUs")
            args.num_instances = instance_num
    else:
        instance_num = args.num_instances

    rope_scaling = args.rope_scaling
    
    # Launch instances
    processes = []
    try:
        for i in range(args.num_instances):
            # Calculate GPU IDs for this instance
            if args.total_gpus:
                gpu_ids = list(range(i * args.tensor_parallel_size, (i + 1) * args.tensor_parallel_size))
            else:
                gpu_ids = None
            
            port = args.start_port + i

            process = launch_single_vllm_server(
                model_path=args.model_path,
                model_name=args.model_name,
                port=port,
                tensor_parallel_size=args.tensor_parallel_size,
                gpu_memory_utilization=args.gpu_memory_utilization,
                max_model_len=args.max_model_len,
                dtype=args.dtype,
                gpu_ids=gpu_ids,
                rope_scaling=rope_scaling,
            )
            processes.append(process)
            logger.info(f"Started instance {i+1}/{args.num_instances} on port {port}")

        logger.info("All VLLM servers started. Press Ctrl+C to stop.")
        while True:
            time.sleep(3600)

    except KeyboardInterrupt:
        logger.info("Shutting down VLLM servers...")
        for process in processes:
            process.terminate()
        sys.exit(0)


if __name__ == "__main__":
    main()

