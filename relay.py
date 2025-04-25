#!/usr/bin/env python3
"""
Supabase Relay Proxy for Supabase MCP Server
This file implements a relay proxy to allow cloud LLMs to access the Supabase MCP server.
"""

import os
import json
import logging
from functools import lru_cache
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, PlainTextResponse
import httpx

# Configure logging
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("supabase-relay")

# Get environment variables
UPSTREAM = os.getenv("UPSTREAM_URL", "https://supabase-mcp-snowy-snow-3355.fly.dev/mcp")
AUTH = ("instabids", "secure123password")

# Create FastAPI app
app = FastAPI(
    title="Supabase Relay",
    description="A relay server for the Supabase MCP server",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for cloud LLMs
    allow_methods=["*"],
    allow_headers=["*"],
)

# Task Master MCP internal endpoint
UPSTREAM = os.getenv("UPSTREAM_URL", "http://localhost:8000/mcp")
AUTH = ("instabids", "secure123password")

@app.post("/proxy/{endpoint:path}")
async def proxy(endpoint: str, request: Request):
    """
    Proxy endpoint that forwards requests to the Task Master MCP server with authentication.
    This allows cloud LLMs to interact with the Task Master MCP server without needing to send auth headers.
    """
    try:
        # Get the request body
        body_bytes = await request.body()
        body_str = body_bytes.decode('utf-8')
        
        # Log the incoming request
        print(f"Received request for endpoint: {endpoint}")
        print(f"Request body: {body_str}")
        
        # Parse the request body
        import json
        try:
            body_json = json.loads(body_str)
            
            # Check if the request follows the function call format
            if "function_call" in body_json:
                function_call = body_json["function_call"]
                function_name = function_call.get("name")
                parameters = function_call.get("parameters", {})
                
                # Ensure the function name matches the endpoint
                if function_name and function_name != endpoint:
                    print(f"Warning: Function name {function_name} doesn't match endpoint {endpoint}")
                
                # Forward just the parameters to the MCP server
                forward_body = json.dumps(parameters)
                print(f"Forwarding to MCP server: {forward_body}")
            else:
                # If not in function call format, forward as-is
                forward_body = body_str
                print("No function_call found, forwarding as-is")
        except json.JSONDecodeError:
            # If not valid JSON, forward as-is
            forward_body = body_str
            print("Invalid JSON, forwarding as-is")
        
        # Forward the request to the Task Master MCP server with authentication
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{UPSTREAM}/{endpoint}",
                content=forward_body,
                headers={"Content-Type": "application/json"},
                auth=AUTH,
                timeout=30  # Increase timeout to 30 seconds
            )
            
            # Get the response from the MCP server
            response_status = response.status_code
            try:
                response_json = response.json()
                print(f"MCP server response: {response_json}")
            except json.JSONDecodeError:
                response_text = response.text
                print(f"MCP server response (not JSON): {response_text}")
                return {"response": response_text, "status": response_status, "error": None}
            
            # Return the response from the Task Master MCP server
            return response_json
    except Exception as e:
        error_msg = str(e)
        print(f"Error in proxy: {error_msg}")
        return {"error": error_msg, "status": 500}

@app.get("/", response_class=HTMLResponse)
def root():
    """Root endpoint that returns HTML documentation"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Supabase Relay API</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }
            h1 { color: #333; }
            h2 { color: #444; margin-top: 30px; }
            pre { background-color: #f4f4f4; padding: 10px; border-radius: 5px; overflow-x: auto; }
            a { color: #0066cc; text-decoration: none; }
            a:hover { text-decoration: underline; }
            .endpoint { margin-bottom: 20px; }
            .description { margin-bottom: 10px; }
        </style>
    </head>
    <body>
        <h1>Supabase Relay API</h1>
        <p>This API provides a relay to the Supabase MCP server for database operations.</p>
        
        <h2>API Documentation</h2>
        <p>View the full API documentation:</p>
        <ul>
            <li><a href="/openapi.json">OpenAPI Specification (JSON)</a></li>
            <li><a href="/openapi.txt">OpenAPI Specification (Text)</a></li>
        </ul>
        
        <h2>Health Check</h2>
        <div class="endpoint">
            <p class="description">Check if the API is healthy:</p>
            <pre>curl -X GET https://supabase-relay.fly.dev/health</pre>
        </div>
        
        <h2>Example Queries</h2>
        <div class="endpoint">
            <h3>Execute SQL Query</h3>
            <p class="description">Run a SQL query against the database:</p>
            <pre>curl -X POST https://supabase-relay.fly.dev/proxy/query \
    -H "Content-Type: application/json" \
    -d '{"function_call": {"name": "query", "parameters": {"sql": "SELECT * FROM users LIMIT 10"}}}'</pre>
        </div>
        
        <div class="endpoint">
            <h3>List Tables</h3>
            <p class="description">List all tables in the database:</p>
            <pre>curl -X POST https://supabase-relay.fly.dev/proxy/list_tables \
    -H "Content-Type: application/json" \
    -d '{"function_call": {"name": "list_tables", "parameters": {}}}'</pre>
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)

@app.get("/health")
async def health_check(request: Request):
    """Health check endpoint"""
    accept_header = request.headers.get("accept", "")
    if "application/health" in accept_header:
        return Response(status_code=204, media_type="application/health+json")
    else:
        return {"ok": True}

@app.get("/openapi.json")
async def get_openapi_schema(request: Request):
    """Return OpenAPI schema for Supabase functions"""
    schema = app.openapi()
    
    # Check if client prefers text format
    accept_header = request.headers.get("accept", "")
    if "text/" in accept_header:
        return Response(content=json.dumps(schema, indent=2), media_type="text/plain; charset=utf-8")
    else:
        return JSONResponse(content=schema, headers={"Content-Type": "application/json"}, gzip=True)

@app.get("/openapi.txt")
@lru_cache(maxsize=1)
def openapi_txt():
    """Return OpenAPI schema as plain text for LLM tooling"""
    schema = app.openapi()
    return PlainTextResponse(
        content=json.dumps(schema, indent=2),
        headers={"Content-Type": "text/plain; charset=utf-8"}
    )

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "80"))
    uvicorn.run(app, host="0.0.0.0", port=port)
