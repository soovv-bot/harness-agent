"""
Subprocess Interpreter for Code Execution
Executes Python code in isolated subprocess environment
"""

import ast
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from loguru import logger


class SubprocessInterpreter:
    """Execute Python code in subprocess."""

    def __init__(
        self,
        print_stdout: bool = False,
        print_stderr: bool = False,
        execution_timeout: int = 300,
    ) -> None:
        """
        Initialize subprocess interpreter.
        
        Args:
            print_stdout: Whether to print stdout
            print_stderr: Whether to print stderr
            execution_timeout: Execution timeout in seconds
        """
        self.print_stdout = print_stdout
        self.print_stderr = print_stderr
        self.execution_timeout = execution_timeout
        self.temp_dir = tempfile.mkdtemp()

    def run_file(self, file: Path) -> str:
        """
        Execute Python file.
        
        Args:
            file: Path to Python file
            
        Returns:
            Execution result as string
        """
        if not file.is_file():
            return f"{file} is not a file."

        # Read and parse Python code
        try:
            with open(file, 'r', encoding='utf-8') as f:
                source = f.read()

            tree = ast.parse(source)
            
            if tree.body:
                last_node = tree.body[-1]
                if isinstance(last_node, ast.Expr):
                    if not (isinstance(last_node.value, ast.Call) and 
                           isinstance(last_node.value.func, ast.Name) and
                           last_node.value.func.id == 'print'):
                        # Wrap the expression in print(repr())
                        tree.body[-1] = ast.Expr(
                            value=ast.Call(
                                func=ast.Name(id='print', ctx=ast.Load()),
                                args=[
                                    ast.Call(
                                        func=ast.Name(id='repr', ctx=ast.Load()),
                                        args=[last_node.value],
                                        keywords=[],
                                    )
                                ],
                                keywords=[],
                            )
                        )
                ast.fix_missing_locations(tree)
                # Convert AST back to source code
                import astor
                modified_source = astor.to_source(tree)
                # Create temporary file
                temp_file = self._create_temp_file(modified_source)
                cmd = ["python", str(temp_file)]
        except Exception as e:
            logger.warning(f"Failed to parse Python code: {e}")
            cmd = ["python", str(file)]

        # Get current Python environment
        env = os.environ.copy()
        if os.name == 'nt':
            python_path = os.path.dirname(sys.executable)
            if 'PATH' in env:
                env['PATH'] = python_path + os.pathsep + env['PATH']
            else:
                env['PATH'] = python_path

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                shell=False,
            )
            stdout, stderr = proc.communicate(timeout=self.execution_timeout)
            return_code = proc.returncode
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            return_code = proc.returncode
            timeout_msg = f"Process timed out after {self.execution_timeout} seconds."
            stderr = f"{stderr}\n{timeout_msg}"

        # Clean up temporary file
        if 'temp_file' in locals():
            try:
                if temp_file.exists():
                    temp_file.unlink()
            except Exception as e:
                logger.warning(f"Failed to clean up temporary file: {e}")

        if self.print_stdout and stdout:
            print("======stdout======")
            print(stdout)
            print("==================")
        if self.print_stderr and stderr:
            print("======stderr======")
            print(stderr)
            print("==================")

        # Build execution result
        exec_result = ""
        if stdout:
            exec_result += stdout
        if stderr:
            exec_result += f"(stderr: {stderr})"
        if return_code != 0:
            error_msg = f"(Execution failed, return code {return_code})"
            if not stderr:
                exec_result += error_msg
            elif error_msg not in stderr:
                exec_result += error_msg
        return exec_result

    def run(self, code: str) -> str:
        """
        Execute Python code string.

        Args:
            code: The code string to execute.

        Returns:
            str: String containing execution results.
        """
        temp_file = None
        try:
            temp_file = self._create_temp_file(code)
            return self.run_file(temp_file)
        finally:
            # Clean up temporary file
            if temp_file and temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary file: {e}")

    def _create_temp_file(self, code: str) -> Path:
        """
        Create a temporary file containing the given code.

        Args:
            code: The code to write into the temporary file.

        Returns:
            Path: The path to the temporary file.
        """
        # Use tempfile to generate a random file name
        temp_file = tempfile.NamedTemporaryFile(suffix='.py', dir=self.temp_dir, delete=False)
        file_path = Path(temp_file.name)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(code)

        return file_path

