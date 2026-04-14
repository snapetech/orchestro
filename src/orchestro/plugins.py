from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

HOOK_PRE_RUN = "pre_run"
HOOK_POST_RUN = "post_run"
HOOK_PRE_TOOL = "pre_tool"
HOOK_POST_TOOL = "post_tool"
HOOK_ON_FAILURE = "on_failure"
HOOK_ON_PLAN_STEP = "on_plan_step"
ALL_HOOKS = {HOOK_PRE_RUN, HOOK_POST_RUN, HOOK_PRE_TOOL, HOOK_POST_TOOL, HOOK_ON_FAILURE, HOOK_ON_PLAN_STEP}


@dataclass(frozen=True, slots=True)
class HookResult:
    action: str  # "continue", "abort", "modify"
    reason: str = ""
    data: dict | None = None


CONTINUE = HookResult("continue")


@dataclass(frozen=True, slots=True)
class PluginMetadata:
    name: str
    version: str = "0.0.0"
    description: str = ""
    author: str = ""


class HookRunner:
    def __init__(self) -> None:
        self._handlers: dict[str, list[tuple[str, Callable]]] = {hook: [] for hook in ALL_HOOKS}
        self.last_errors: list[dict[str, str]] = []

    def on(self, hook: str, handler: Callable, *, plugin_name: str = "unknown") -> None:
        if hook not in ALL_HOOKS:
            raise ValueError(f"Unknown hook: {hook}")
        self._handlers[hook].append((plugin_name, handler))

    def run(self, hook: str, context: dict) -> HookResult:
        self.last_errors = []
        for plugin_name, handler in self._handlers.get(hook, []):
            try:
                result = handler(context)
                if isinstance(result, HookResult):
                    if result.action == "abort":
                        return result
                    if result.action == "modify" and result.data:
                        context.update(result.data)
            except Exception as exc:
                self.last_errors.append({
                    "hook": hook,
                    "plugin": plugin_name,
                    "error": str(exc),
                })
        return CONTINUE

    def list_handlers(self) -> dict[str, list[str]]:
        return {hook: [name for name, _ in handlers] for hook, handlers in self._handlers.items() if handlers}


class PluginManager:
    def __init__(self, plugins_dir: Path | None = None) -> None:
        self.plugins_dir = plugins_dir
        self.hooks = HookRunner()
        self.loaded: list[PluginMetadata] = []
        self.load_errors: list[dict[str, str]] = []

    def load_all(self) -> None:
        if self.plugins_dir is None or not self.plugins_dir.is_dir():
            return
        for path in sorted(self.plugins_dir.iterdir()):
            if path.suffix == ".py" and not path.name.startswith("_"):
                self._load_plugin(path)

    def _load_plugin(self, path: Path) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location(f"orchestro_plugin_{path.stem}", path)
        if spec is None or spec.loader is None:
            return
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            self.load_errors.append({"plugin": path.stem, "error": str(exc)})
            return
        register_fn = getattr(module, "register", None)
        if callable(register_fn):
            register_fn(self.hooks)
        metadata = getattr(module, "METADATA", None)
        if isinstance(metadata, PluginMetadata):
            self.loaded.append(metadata)
        else:
            self.loaded.append(PluginMetadata(name=path.stem))
