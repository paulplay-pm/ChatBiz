from fastapi import APIRouter, Depends, HTTPException
from app.nodes.registry import NODE_REGISTRY
from app.api.deps import get_user_id

router = APIRouter(prefix="/api/nodes", tags=["nodes"])


@router.get("")
async def list_node_types(
    _user_id: str = Depends(get_user_id),
):
    """List all registered node types + their versions. Auth via shared dep."""
    return {
        "node_types": [
            {"type": t, "version": NODE_REGISTRY[t].version}
            for t in sorted(NODE_REGISTRY.keys())
        ]
    }


@router.get("/{type_name}/schema")
async def get_node_schema(
    type_name: str,
    _user_id: str = Depends(get_user_id),
):
    """Return JSON schema for a specific node type. Used by implement-canvas-ui."""
    if type_name not in NODE_REGISTRY:
        raise HTTPException(status_code=404, detail={"error_class": "user", "error_message": f"节点类型 {type_name!r} 未注册"})
    return NODE_REGISTRY[type_name].schema()
