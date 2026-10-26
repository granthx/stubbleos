"""Versioned prompt registry. Prompts are data, not inline strings.

Templates use ``string.Template`` ($var) so JSON braces in prompts need no escaping.
Rendering is strict: missing *and* unexpected variables are errors.
"""

from __future__ import annotations

from string import Template

from stubbleos.core.types import FrozenModel, Language


class PromptError(Exception):
    pass


class PromptNotFoundError(PromptError, KeyError):
    pass


PromptNotFound = PromptNotFoundError


class PromptTemplate(FrozenModel):
    name: str
    version: int
    template: str
    language: Language | None = None
    description: str = ""

    @property
    def ref(self) -> str:
        suffix = f":{self.language.value}" if self.language else ""
        return f"{self.name}@v{self.version}{suffix}"

    @property
    def variables(self) -> frozenset[str]:
        return frozenset(Template(self.template).get_identifiers())


class RenderedPrompt(FrozenModel):
    text: str
    ref: str


class PromptRegistry:
    def __init__(self) -> None:
        self._items: dict[tuple[str, int, Language | None], PromptTemplate] = {}

    def register(self, prompt: PromptTemplate) -> PromptTemplate:
        if not Template(prompt.template).is_valid():
            raise PromptError(f"{prompt.ref}: invalid $-placeholder in template")
        key = (prompt.name, prompt.version, prompt.language)
        if key in self._items:
            raise PromptError(f"{prompt.ref} already registered; bump the version instead")
        self._items[key] = prompt
        return prompt

    def get(
        self, name: str, *, version: int | None = None, language: Language | None = None
    ) -> PromptTemplate:
        candidates = [p for p in self._items.values() if p.name == name]
        if version is not None:
            candidates = [p for p in candidates if p.version == version]
        elif candidates:
            latest = max(p.version for p in candidates)
            candidates = [p for p in candidates if p.version == latest]
        if language is not None:
            exact = [p for p in candidates if p.language == language]
            if exact:
                return exact[0]
        generic = [p for p in candidates if p.language is None]
        if generic:
            return generic[0]
        raise PromptNotFound(f"no prompt {name!r} version={version} language={language}")

    def render(
        self,
        name: str,
        *,
        version: int | None = None,
        language: Language | None = None,
        **variables: str,
    ) -> RenderedPrompt:
        prompt = self.get(name, version=version, language=language)
        missing = prompt.variables - variables.keys()
        extra = variables.keys() - prompt.variables
        if missing or extra:
            raise PromptError(f"{prompt.ref}: missing={sorted(missing)} unexpected={sorted(extra)}")
        return RenderedPrompt(text=Template(prompt.template).substitute(variables), ref=prompt.ref)

    def names(self) -> list[str]:
        return sorted({k[0] for k in self._items})


default_registry = PromptRegistry()
