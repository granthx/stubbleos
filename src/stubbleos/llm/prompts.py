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

# --------------------------------------------------------------------------- Standard dialogue prompts

# Generic fallback responses
default_registry.register(
    PromptTemplate(
        name="farmer_voice_response",
        version=1,
        language=Language.ENGLISH,
        template="You are StubbleOS assistant. Respond helpfully and concisely to the farmer: $user_text",
        description="General response prompt in English",
    )
)
default_registry.register(
    PromptTemplate(
        name="farmer_voice_response",
        version=1,
        language=Language.PUNJABI,
        template="ਤੁਸੀਂ ਸਟੱਬਲਓਐਸ ਦੇ ਸਹਾਇਕ ਹੋ। ਕਿਸਾਨ ਦੀ ਬੇਨਤੀ ਦਾ ਨਿਮਰਤਾ ਨਾਲ ਜਵਾਬ ਦਿਓ: $user_text",
        description="General response prompt in Punjabi",
    )
)
default_registry.register(
    PromptTemplate(
        name="farmer_voice_response",
        version=1,
        language=Language.HINDI,
        template="आप स्टबलओएस के सहायक हैं। किसान के अनुरोध का विनम्रता से उत्तर दें: $user_text",
        description="General response prompt in Hindi",
    )
)

# Greetings
default_registry.register(
    PromptTemplate(
        name="farmer_voice_greeting",
        version=1,
        language=Language.ENGLISH,
        template="Hello! Welcome to StubbleOS crop residue management service. How can we help you today with machine booking or straw management?",
        description="Greeting message in English",
    )
)
default_registry.register(
    PromptTemplate(
        name="farmer_voice_greeting",
        version=1,
        language=Language.PUNJABI,
        template="ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ ਜੀ! ਸਟੱਬਲਓਐਸ ਪਰਾਲੀ ਪ੍ਰਬੰਧਨ ਸੇਵਾ ਵਿੱਚ ਤੁਹਾਡਾ ਸਵਾਗਤ ਹੈ। ਅੱਜ ਅਸੀਂ ਮਸ਼ੀਨ ਬੁਕਿੰਗ ਜਾਂ ਪਰਾਲੀ ਸਾਂਭਣ ਵਿੱਚ ਤੁਹਾਡੀ ਕਿਵੇਂ ਮਦਦ ਕਰ ਸਕਦੇ ਹਾਂ?",
        description="Greeting message in Punjabi",
    )
)
default_registry.register(
    PromptTemplate(
        name="farmer_voice_greeting",
        version=1,
        language=Language.HINDI,
        template="नमस्ते! स्टबलओएस पराली प्रबंधन सेवा में आपका स्वागत है। मशीन बुकिंग या पराली प्रबंधन में हम आपकी क्या सहायता कर सकते हैं?",
        description="Greeting message in Hindi",
    )
)

# Missing slot prompt
default_registry.register(
    PromptTemplate(
        name="farmer_voice_slot_prompt",
        version=1,
        language=Language.ENGLISH,
        template="To complete your $machine_type booking, please tell us: $missing_slot.",
        description="Slot filling question in English",
    )
)
default_registry.register(
    PromptTemplate(
        name="farmer_voice_slot_prompt",
        version=1,
        language=Language.PUNJABI,
        template="ਤੁਹਾਡੀ $machine_type ਦੀ ਬੁਕਿੰਗ ਪੂਰੀ ਕਰਨ ਲਈ, ਕਿਰਪਾ ਕਰਕੇ ਦੱਸੋ: $missing_slot.",
        description="Slot filling question in Punjabi",
    )
)
default_registry.register(
    PromptTemplate(
        name="farmer_voice_slot_prompt",
        version=1,
        language=Language.HINDI,
        template="आपकी $machine_type बुकिंग पूरी करने के लिए, कृपया बताएं: $missing_slot.",
        description="Slot filling question in Hindi",
    )
)

# Booking confirmation
default_registry.register(
    PromptTemplate(
        name="farmer_voice_booking_confirm",
        version=1,
        language=Language.ENGLISH,
        template="Your booking for $machine_type on $acres acres in $village for $date is ready. Estimated rate is ₹$net_price. Please reply YES to confirm.",
        description="Booking confirmation in English",
    )
)
default_registry.register(
    PromptTemplate(
        name="farmer_voice_booking_confirm",
        version=1,
        language=Language.PUNJABI,
        template="ਪਿੰਡ $village ਵਿੱਚ $acres ਏਕੜ ਲਈ $date ਨੂੰ $machine_type ਦੀ ਬੁਕਿੰਗ ਤਿਆਰ ਹੈ। ਅੰਦਾਜ਼ਨ ਦਰ ₹$net_price ਹੈ। ਪੁਸ਼ਟੀ ਕਰਨ ਲਈ ਹਾਂ ਜਾਂ 1 ਦਬਾਓ।",
        description="Booking confirmation in Punjabi",
    )
)
default_registry.register(
    PromptTemplate(
        name="farmer_voice_booking_confirm",
        version=1,
        language=Language.HINDI,
        template="गाँव $village में $acres एकड़ के लिए $date को $machine_type की बुकिंग तैयार है। अनुमानित दर ₹$net_price है। पुष्टि के लिए हाँ या 1 दबाएँ।",
        description="Booking confirmation in Hindi",
    )
)

# Burn threat de-escalation
default_registry.register(
    PromptTemplate(
        name="farmer_voice_burn_threat_deescalation",
        version=1,
        language=Language.ENGLISH,
        template="Veerji, please do not set fire to the field. Our local field officer is being notified urgently with high priority to dispatch a machine immediately.",
        description="De-escalation response in English",
    )
)
default_registry.register(
    PromptTemplate(
        name="farmer_voice_burn_threat_deescalation",
        version=1,
        language=Language.PUNJABI,
        template="ਵੀਰ ਜੀ, ਕਿਰਪਾ ਕਰਕੇ ਖੇਤ ਨੂੰ ਅੱਗ ਨਾ ਲਗਾਓ। ਸਾਡੀ ਟੀਮ ਤੁਹਾਡੀ ਮਦਦ ਲਈ ਤੁਰੰਤ ਮਸ਼ੀਨ ਭੇਜਣ ਦਾ ਪ੍ਰਬੰਧ ਕਰ ਰਹੀ ਹੈ ਅਤੇ ਫੀਲਡ ਅਧਿਕਾਰੀ ਨੂੰ ਸੂਚਿਤ ਕਰ ਦਿੱਤਾ ਗਿਆ ਹੈ।",
        description="De-escalation response in Punjabi",
    )
)
default_registry.register(
    PromptTemplate(
        name="farmer_voice_burn_threat_deescalation",
        version=1,
        language=Language.HINDI,
        template="किसान भाई, कृपया खेत में आग न लगाएँ। हमारी टीम प्राथमिकता के आधार पर तुरंत मशीन की व्यवस्था कर रही है और अधिकारी को सूचित कर दिया गया है।",
        description="De-escalation response in Hindi",
    )
)

# Pricing counter-offer
default_registry.register(
    PromptTemplate(
        name="pricing_counter_offer",
        version=1,
        language=Language.ENGLISH,
        template="Buyer offered ₹$offered_price/t for $tonnes t ($delivery_term). Counter-offer generated: ₹$counter_price/t. Rationale: $rationale",
        description="Pricing counter offer explanation",
    )
)
default_registry.register(
    PromptTemplate(
        name="pricing_counter_offer",
        version=1,
        language=Language.PUNJABI,
        template="ਖਰੀਦਦਾਰ ਨੇ ₹$offered_price ਪ੍ਰਤੀ ਟਨ ਪੇਸ਼ਕਸ਼ ਕੀਤੀ ਹੈ। ਜਵਾਬੀ ਪੇਸ਼ਕਸ਼: ₹$counter_price ਪ੍ਰਤੀ ਟਨ। ਕਾਰਨ: $rationale",
        description="Pricing counter offer explanation in Punjabi",
    )
)
default_registry.register(
    PromptTemplate(
        name="pricing_counter_offer",
        version=1,
        language=Language.HINDI,
        template="खरीदार ने ₹$offered_price प्रति टन का प्रस्ताव दिया। जवाबी प्रस्ताव: ₹$counter_price प्रति टन। कारण: $rationale",
        description="Pricing counter offer explanation in Hindi",
    )
)
