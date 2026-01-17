import subprocess
import json
import uuid
import time
import os

class AgentBrowserInterface:
    def __init__(self, session_name=None):
        # Use a shorter session name to avoid socket path length limits
        self.session_name = session_name or f"sess-{uuid.uuid4().hex[:12]}"
        
        # Prefer local binary if available
        local_bin = os.path.join("node_modules", ".bin", "agent-browser")
        if os.path.exists(local_bin):
            self.base_cmd = [local_bin, "--session", self.session_name]
        else:
            self.base_cmd = ["npx", "agent-browser", "--session", self.session_name]
        
    def _run(self, cmd_args, debug=False):
        full_cmd = self.base_cmd + cmd_args
        if debug:
            print(f"Executing: {' '.join(full_cmd)}")
            
        try:
            # Ensure PATH includes node_modules/.bin
            env = os.environ.copy()
            local_bin_dir = os.path.join(os.getcwd(), "node_modules", ".bin")
            env["PATH"] = f"{local_bin_dir}:{env.get('PATH', '')}"
            
            result = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                check=False,
                env=env,
                cwd=os.getcwd()
            )
            if result.returncode != 0:
                print(f"Command failed: {' '.join(full_cmd)}")
                print(f"Error: {result.stderr}")
                return None
            return result.stdout.strip()
        except Exception as e:
            print(f"Exception executing command: {e}")
            return None

    def open(self, url):
        return self._run(["open", url])

    def scroll(self, direction="down", pixels=None):
        args = ["scroll", direction]
        if pixels:
            args.append(str(pixels))
        return self._run(args)

    def wait(self, duration_ms):
        # Using python sleep might be better than keeping the CLI busy, 
        # but the CLI also has a wait command which might wait for network idle?
        # Usage: wait <sel|ms>
        return self._run(["wait", str(duration_ms)])

    def get_html(self):
        # Usage: agent-browser get html [selector]
        # Error: Missing arguments for: get html
        return self._run(["get", "html", "html"])
    
    def click(self, selector):
        return self._run(["click", selector])

    def evaluate(self, js_code):
        # Usage: agent-browser eval <js>
        return self._run(["eval", js_code])

    def set_cookie(self, cookie):
        # agent-browser cookies set <name> <value> [options]
        # It seems the CLI might handle simple set. Let's check help again or assume standard args.
        # Help said: cookies [get|set|clear]
        # Detailed usage is likely: cookies set name value --domain ...
        # But we will try to pass minimal args or multiple commands.
        # Let's assume: agent-browser cookies set name value
        cmd = ["cookies", "set", cookie['name'], cookie['value']]
        # TODO: Support domain/path if CLI supports flags for them.
        # For now, let's hope setting name/value is enough for the active domain (x.com).
        # But we must be ON the domain to set cookies usually.
        return self._run(cmd)

    def screenshot(self, path):
        return self._run(["screenshot", path, "--full"])

    def close(self):
        return self._run(["close"])
        
    def install(self):
        """Run install if needed."""
        # Note: This might require interaction (y/n), so better run manually if not installed.
        pass
