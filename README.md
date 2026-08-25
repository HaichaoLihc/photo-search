# Photo Search

Local semantic photo search backed by SigLIP2 embeddings. The project includes a
browser UI/API and a read-only MCP server designed for vision-capable agents.

## MCP tools

- `search_photo_contact_sheet(query, count=25, threshold=0.0)` searches the index
  and returns one compact five-column PNG containing 10–50 ranked photos. A JSON
  manifest maps each 1-based row and column to a stable `photo_id`.
- `get_photo(photo_id, max_edge=1600)` returns a larger preview for a shortlisted
  image.
- `photo_search_stats()` reports index and model status.

The server never modifies or deletes photos.

## Install

```bash
cd /Users/haichaoli/Documents/my-apps/photo-search
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Create the index if needed:

```bash
.venv/bin/python index.py /absolute/path/to/photos
```

## Run the MCP server

The server uses stdio, so configure the MCP client to launch it rather than
running it in a normal interactive terminal.

```json
{
  "mcpServers": {
    "photo-search": {
      "command": "/Users/haichaoli/Documents/my-apps/photo-search/.venv/bin/python",
      "args": [
        "/Users/haichaoli/Documents/my-apps/photo-search/mcp_server.py"
      ]
    }
  }
}
```

For Codex CLI, add:

```toml
[mcp_servers.photo-search]
command = "/Users/haichaoli/Documents/my-apps/photo-search/.venv/bin/python"
args = ["/Users/haichaoli/Documents/my-apps/photo-search/mcp_server.py"]
```

The first tool call loads the SigLIP2 model. Later searches reuse it in memory.

## Run the web app

```bash
.venv/bin/python run_server.py
```

Open <http://127.0.0.1:8000>.

## Test

```bash
.venv/bin/python -m unittest discover -s tests -v
```
