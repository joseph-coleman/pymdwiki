# jupyter_client.py
import json
import uuid
import asyncio
import httpx
import websockets
from datetime import datetime, timezone

JUPYTER_HOST = "http://jupyter:8888"  # Hostname defined in docker-compose
JUPYTER_WS = "ws://jupyter:8888"


class AsyncJupyterManager(object):
    def __init__(self):
        # In-memory store: { "page_id": "kernel_uuid" }
        self.kernels = {}

    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = super(AsyncJupyterManager, cls).__new__(cls)
        return cls.instance

    async def get_or_create_kernel(self, page_id: str):
        """
        Checks if a kernel exists for the page. If not, creates one.
        """
        if page_id in self.kernels:
            # Optionally verify kernel is still alive via API here
            return self.kernels[page_id]

        async with httpx.AsyncClient() as client:
            # Spawn a new kernel
            response = await client.post(f"{JUPYTER_HOST}/api/kernels")
            if response.status_code == 201:
                kernel_id = response.json()["id"]
                self.kernels[page_id] = kernel_id
                return kernel_id
            else:
                raise Exception(f"Failed to spawn kernel: {response.text}")

    async def list_kernels(self, max_age_seconds=3600):

        kernel_list = []

        async with httpx.AsyncClient() as client:
            try:
                # 1. Get list of running kernels from Docker service
                response = await client.get(f"{JUPYTER_HOST}/api/kernels")
                if response.status_code != 200:
                    kernel_list = "Error fetching kernels from Jupyter"
                    # await asyncio.sleep(1)
                    return kernel_list

                active_kernels = response.json()

                for kernel in active_kernels:
                    kernel_id = kernel["id"]
                    print("list kernel ", kernel)
                    last_activity_str = kernel["last_activity"]

                    # Parse ISO 8601 string (Handle 'Z' manually if on older Python)
                    # Example: "2023-11-19T12:00:00.000000Z"
                    last_activity = datetime.fromisoformat(
                        last_activity_str.replace("Z", "+00:00")
                    )
                    now = datetime.now(timezone.utc)

                    idle_seconds = (now - last_activity).total_seconds()

                    page_list = []
                    for each_page in self.kernels:
                        if kernel_id == self.kernels[each_page]:
                            page_list.append(each_page)

                    kc = kernel.copy()
                    kc.update({"pages": page_list, "idle": idle_seconds})
                    print(kc)
                    kernel_list.append(
                        kc
                        # kernel.update({"pages": page_list, "idle": idle_seconds})
                        # {"pages": page_list, "idle": idle_seconds}.update(kernel)
                    )

            except Exception as e:
                kernel_list = f"List error: {e}"

            # await asyncio.sleep(1)
        return kernel_list

    async def delete_kernel_by_id(self, kernel_id):
        async with httpx.AsyncClient() as client:
            try:
                await self._delete_kernel(client, kernel_id)
            except Exception as e:
                print(f"Error deleting kernel: {e}")

    def wrap_msg(self, msg_type, msg_data):
        return json.dumps({msg_type: msg_data})

    async def execute_code_stream(self, kernel_id: str, code: str):
        """
        Yields output chunks as they arrive from Jupyter.
        """
        ws_url = f"{JUPYTER_WS}/api/kernels/{kernel_id}/channels"

        async with websockets.connect(ws_url) as ws:
            msg_id = uuid.uuid4().hex

            # Send Execute Request
            message = {
                "header": {
                    "msg_id": msg_id,
                    "username": "wiki_user",
                    "session": uuid.uuid4().hex,
                    "msg_type": "execute_request",
                    # "version": "5.3",
                    "date": datetime.now(timezone.utc).isoformat(),
                },
                "parent_header": {},
                "metadata": {},
                "content": {
                    "code": code,
                    "silent": False,
                    "store_history": True,
                    "stop_on_error": True,
                },
            }
            await ws.send(json.dumps(message))

            # Stream Results
            while True:
                response = await ws.recv()
                msg = json.loads(response)

                # Filter messages unrelated to our request
                if msg["parent_header"].get("msg_id") != msg_id:
                    continue

                msg_type = msg["msg_type"]
                content = msg["content"]
                # print("_____________________________")
                # print(msg)

                # Standard Output (print statements)
                if msg_type == "stream":
                    # yield content["text"]
                    d = content["text"]
                    d = d.replace("\n", "<br/>")
                    yield self.wrap_msg("html", d)

                # Errors
                elif msg_type == "error":
                    d = f"<pre>Error: {content['evalue']}</pre>"
                    yield self.wrap_msg("html", d)

                #
                elif (msg_type == "execute_result") | (msg_type == "display_data"):
                    data = content["data"]
                    # print(data)
                    if (d := data.get("text/plain")) and not data.get(
                        "application/vnd.jupyter.widget-view+json"
                    ):
                        # print("this looks like TEXT ", d)
                        # this doesn't seem to be getting called anymore.
                        d = f"<pre>{d}</pre>"
                        yield self.wrap_msg("html", d)

                    if d := data.get("text/html"):
                        # print("this looks like HTML", d)
                        yield self.wrap_msg("html", d)
                    if d := data.get("image/png"):
                        d = f'<img src="data:image/png;base64,{d}">'
                        yield self.wrap_msg("html", d)
                    if d := data.get("image/svg+xml"):
                        yield self.wrap_msg("html", d)
                    # //  ipywidgets  // not working
                    # if viewSpec := data.get("application/vnd.jupyter.widget-view+json"):
                    #     #print("~_~_~_~_~_~_~_~_~_~_~_~_~_~")
                    #     ## print(msg)
                    #     #print(data)
                    #     #print(viewSpec)
                    #     #print("+#+#+#+#+#+#+#+#+#+#+#+#+#+")
                    #     ## yield json.dumps({"hello": "world"})

                    #     modelId = viewSpec["model_id"]
                    #     d = f"""
                    #     <script>
                    #         const mgr = await ensureWidgetManager();
                    #         const model = await mgr.get_model("{modelId}");

                    #        if (model):
                    #           const w = await mgr.create_view(model);
                    #           await mgr.display_view(undefined, w, {{ el: this}});
                    #     </script>
                    #     """

                    #     yield self.wrap_msg("js", d)

                # Execution Finished
                elif msg_type == "status":
                    if content["execution_state"] == "idle":
                        break

    async def prune_stale_kernels(self, max_age_seconds=3600):
        """
        Query Jupyter for active kernels, check their last_activity,
        and kill them if they are too old.
        """
        print(f"[{datetime.now()}] 🧹 Reaper running...")

        async with httpx.AsyncClient() as client:
            try:
                # 1. Get list of running kernels from Docker service
                response = await client.get(f"{JUPYTER_HOST}/api/kernels")
                if response.status_code != 200:
                    print("Error fetching kernels from Jupyter")
                    return

                active_kernels = response.json()

                for kernel in active_kernels:
                    kernel_id = kernel["id"]
                    last_activity_str = kernel["last_activity"]

                    # Parse ISO 8601 string (Handle 'Z' manually if on older Python)
                    # Example: "2023-11-19T12:00:00.000000Z"
                    last_activity = datetime.fromisoformat(
                        last_activity_str.replace("Z", "+00:00")
                    )
                    now = datetime.now(timezone.utc)

                    idle_seconds = (now - last_activity).total_seconds()

                    print(kernel_id, idle_seconds)

                    if idle_seconds > max_age_seconds:
                        print(
                            f"💀 Killing stale kernel {kernel_id} (Idle: {idle_seconds:.0f}s)"
                        )
                        await self._delete_kernel(client, kernel_id)

            except Exception as e:
                print(f"Reaper error: {e}")

    async def _delete_kernel(self, client, kernel_id):
        # remove kernel from jupyter server
        await client.delete(f"{JUPYTER_HOST}/api/kernels/{kernel_id}")

        # We must find which page owns this kernel_id
        pages_to_remove = [
            page for page, k_id in self.kernels.items() if k_id == kernel_id
        ]

        for page in pages_to_remove:
            del self.kernels[page]
            print(f"   - Unmapped from page: {page}")


# Singleton instance for the app
jupyter_manager = AsyncJupyterManager()
