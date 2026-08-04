/** Conversational Mira review coaching — local turns + optional Gemini draft. */

const STAR_LABELS = {
  1: "Not for me",
  2: "A bit off",
  3: "It's okay",
  4: "Really liked it",
  5: "Obsessed",
};

const FIT_PHRASE = {
  tight: "runs a little snug",
  true: "is true to size",
  loose: "has a relaxed, easy fit",
};

export function starLabel(stars) {
  return STAR_LABELS[stars] || STAR_LABELS[5];
}

export function parseStars(text) {
  const t = (text || "").trim().toLowerCase();
  const digit = t.match(/\b([1-5])\s*(?:star|stars|\/\s*5)?\b/);
  if (digit) return Number(digit[1]);
  if (/\b(five|obsessed|love[d]? it|amazing|perfect)\b/.test(t)) return 5;
  if (/\b(four|really liked|great|loved)\b/.test(t)) return 4;
  if (/\b(three|okay|ok|fine|average|alright)\b/.test(t)) return 3;
  if (/\b(two|meh|bit off|disappointed)\b/.test(t)) return 2;
  if (/\b(one|hate|terrible|awful|not for me)\b/.test(t)) return 1;
  for (const [n, label] of Object.entries(STAR_LABELS)) {
    if (t === label.toLowerCase()) return Number(n);
  }
  return null;
}

export function parseFit(text) {
  const t = (text || "").trim().toLowerCase();
  if (/\b(tight|snug|small|sized?\s*up|runs small)\b/.test(t)) return "tight";
  if (/\b(loose|relaxed|roomy|baggy|big|sized?\s*down|runs large)\b/.test(t)) return "loose";
  if (/\b(true|perfect fit|usual|normal|exact|right)\b/.test(t)) return "true";
  if (t === "runs tight") return "tight";
  if (t === "runs loose") return "loose";
  if (t === "true to size") return "true";
  return null;
}

function shortName(product) {
  const name = product?.name || "this piece";
  return name.length > 36 ? `${name.slice(0, 34)}…` : name;
}

/** Opening Mira line for a product. */
export function reviewChatOpen(product) {
  const cat = product?.category || "piece";
  return {
    phase: "stars",
    mira: `Okay — quick review of ${shortName(product)}. How many stars would you give this ${cat}? You can type a number or just say how you feel.`,
    shortcuts: [
      { label: "★★★★★ Obsessed", value: "5 — Obsessed" },
      { label: "★★★★ Really liked it", value: "4 — Really liked it" },
      { label: "★★★ It's okay", value: "3 — It's okay" },
      { label: "★★ A bit off", value: "2 — A bit off" },
    ],
  };
}

/**
 * Advance one conversational turn.
 * returns { phase, mira, shortcuts, answers, draft?, done? }
 */
export function reviewChatTurn({ product, phase, answers, userText }) {
  const text = (userText || "").trim();
  const next = { ...answers, notes: [...(answers.notes || [])] };
  const cat = product?.category || "piece";

  if (phase === "stars") {
    const stars = parseStars(text);
    if (!stars) {
      return {
        phase: "stars",
        mira: "Give me a vibe from 1–5 — even “loved it” or “just okay” works.",
        shortcuts: [
          { label: "5 · Obsessed", value: "5" },
          { label: "4 · Really liked", value: "4" },
          { label: "3 · Okay", value: "3" },
          { label: "2 · A bit off", value: "2" },
        ],
        answers: next,
      };
    }
    next.stars = stars;
    return {
      phase: "fit",
      mira: `${starLabel(stars)} — got it. How was the fit on you? Snug, true to size, or roomy?`,
      shortcuts: [
        { label: "Runs tight", value: "Runs tight" },
        { label: "True to size", value: "True to size" },
        { label: "Runs loose", value: "Runs loose" },
      ],
      answers: next,
    };
  }

  if (phase === "fit") {
    const fit = parseFit(text);
    if (!fit) {
      return {
        phase: "fit",
        mira: "Was it snug, true to your usual size, or a bit loose/roomy?",
        shortcuts: [
          { label: "Runs tight", value: "Runs tight" },
          { label: "True to size", value: "True to size" },
          { label: "Runs loose", value: "Runs loose" },
        ],
        answers: next,
      };
    }
    next.fit = fit;
    next.notes.push(text);
    return {
      phase: "detail",
      mira: `Fit ${FIT_PHRASE[fit]} — thanks. What stood out most? Fabric, colour, comfort, when you'd wear it… type it in your own words.`,
      shortcuts: [
        { label: "Soft fabric", value: "The fabric felt really soft" },
        { label: "Colour pop", value: "The colour looked better in person" },
        { label: "Super comfy", value: "Really comfortable to wear all day" },
        { label: "Great for brunch", value: "I'd wear this to brunch or a casual evening out" },
      ],
      answers: next,
    };
  }

  if (phase === "detail") {
    if (text.length < 2) {
      return {
        phase: "detail",
        mira: "Even a short note helps — fabric, colour, comfort, or an occasion you'd wear it.",
        shortcuts: [
          { label: "Soft fabric", value: "The fabric felt really soft" },
          { label: "Colour pop", value: "The colour looked better in person" },
          { label: "Worth the price", value: "Felt worth the price for me" },
        ],
        answers: next,
      };
    }
    next.notes.push(text);
    return {
      phase: "more",
      mira: "Nice. Anything else — would you buy it again, or skip? Or say “that's all” and I'll draft the review.",
      shortcuts: [
        { label: "I'd buy again", value: "I'd buy this again" },
        { label: "Maybe on sale", value: "I'd wait for a sale next time" },
        { label: "That's all", value: "that's all" },
      ],
      answers: next,
    };
  }

  if (phase === "more") {
    const doneEarly = /^(that'?s all|done|nothing|no|skip|draft|finish)\b/i.test(text);
    if (!doneEarly && text.length >= 2) {
      next.notes.push(text);
    }
    const draft = assembleDraft({ product, answers: next });
    return {
      phase: "draft",
      mira: "Here's your review in your words — tweak anything, add a photo if you want, then post.",
      shortcuts: [],
      answers: next,
      draft,
      done: false,
    };
  }

  if (phase === "draft") {
    // User editing via chat — treat as draft rewrite instruction
    if (text && !/^(post|submit|looks good|ok|okay|done)$/i.test(text)) {
      next.notes.push(text);
      const draft = text.length > 40 ? text.slice(0, 280) : assembleDraft({ product, answers: next });
      return {
        phase: "draft",
        mira: "Updated. Want another tweak, or ready to post?",
        shortcuts: [
          { label: "Looks good — post", value: "post" },
          { label: "Make it shorter", value: "Make it shorter and punchier" },
        ],
        answers: next,
        draft,
      };
    }
    return {
      phase: "draft",
      mira: "Ready when you are — hit Post review.",
      shortcuts: [],
      answers: next,
      draft: assembleDraft({ product, answers: next }),
      submit: /^(post|submit|looks good|ok|okay|done)$/i.test(text),
    };
  }

  return {
    phase,
    mira: `Tell me more about this ${cat}.`,
    shortcuts: [],
    answers: next,
  };
}

export function assembleDraft({ product, answers }) {
  const stars = answers.stars || 5;
  const fit = answers.fit || "true";
  const cat = product?.category || "piece";
  const notes = (answers.notes || []).filter(Boolean);
  // Prefer the user's own detail notes over boilerplate
  const detail = notes
    .filter((n) => !parseFit(n) && !parseStars(n))
    .map((n) => n.replace(/^[.\s]+|[.\s]+$/g, ""))
    .filter((n) => n.length > 1);

  const opener =
    stars >= 5 ? `Obsessed with this ${cat}.`
      : stars >= 4 ? `Really liked this ${cat}.`
        : stars >= 3 ? `Solid ${cat} overall.`
          : stars >= 2 ? `Mixed feelings on this ${cat}.`
            : `Wasn't for me.`;

  const fitLine = `Fit ${FIT_PHRASE[fit] || "is true to size"}.`;
  const body = detail.length
    ? detail.slice(0, 3).map((d) => (/[.!?]$/.test(d) ? d : `${d}.`)).join(" ")
    : stars >= 4
      ? "Comfortable and easy to style."
      : "Depends on what you need it for.";

  let draft = `${opener} ${fitLine} ${body}`.replace(/\s+/g, " ").trim();
  if (draft.length > 280) draft = `${draft.slice(0, 277)}…`;
  return draft;
}

/** Fetch AI-polished draft from server; falls back to assembleDraft. */
export async function fetchReviewDraft({ product, answers, draft }) {
  const localDraft = draft || assembleDraft({ product, answers });
  try {
    const q = new URLSearchParams({
      product_id: product?.id || "",
      stars: String(answers.stars || 5),
      fit: answers.fit || "true",
      vibes: "",
      draft: [
        ...(answers.notes || []),
        localDraft,
      ].join(" | ").slice(0, 280),
      mode: "chat_draft",
    });
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 8000);
    const res = await fetch(`/api/review-assist?${q}`, { signal: ctrl.signal });
    clearTimeout(timer);
    if (!res.ok) return { draft: localDraft, source: "local" };
    const data = await res.json();
    return {
      draft: (data.draft || localDraft).slice(0, 280),
      coach: data.coach || null,
      source: data.source || "api",
    };
  } catch {
    return { draft: localDraft, source: "local" };
  }
}
