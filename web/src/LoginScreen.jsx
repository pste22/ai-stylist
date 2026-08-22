import { useEffect, useState } from "react";
import ForBrands from "./ForBrands.jsx";
import { fetchEnabledProviders } from "./supabaseClient.js";

/** OAuth buttons shared by the home sheet and in-app prompts (VTO). */
export function AuthButtons({ onGoogle, onFacebook, onGithub, authError }) {
  const [providers, setProviders] = useState(null);

  useEffect(() => {
    let active = true;
    fetchEnabledProviders().then((p) => { if (active) setProviders(p); });
    return () => { active = false; };
  }, []);

  const enabled = (name) => providers === null || providers[name] !== false;

  return (
    <>
      {authError && (
        <p className="login-error" role="alert">{authError}</p>
      )}
      <div className="login-actions">
        {enabled("google") && (
          <button type="button" className="oauth-btn oauth-google" onClick={onGoogle}>
            <GoogleIcon />
            Continue with Google
          </button>
        )}
        {enabled("github") && (
          <button type="button" className="oauth-btn oauth-github" onClick={onGithub}>
            <GithubIcon />
            Continue with GitHub
          </button>
        )}
        {enabled("facebook") && (
          <button type="button" className="oauth-btn oauth-facebook" onClick={onFacebook}>
            <FacebookIcon />
            Continue with Facebook
          </button>
        )}
      </div>
    </>
  );
}

export default function LoginScreen({
  onGoogle, onFacebook, onGithub, onGuest,
  autoOpen = false, authError = null, onDismissError,
}) {
  const [showAuth, setShowAuth] = useState(autoOpen);
  const [showBrands, setShowBrands] = useState(false);
  const [prompt, setPrompt] = useState("");

  // An error only makes sense next to the buttons that produced it.
  useEffect(() => { if (authError) setShowAuth(true); }, [authError]);

  const closeAuth = () => { setShowAuth(false); onDismissError?.(); };

  useEffect(() => {
    if (!showAuth) return;
    const onKey = (e) => { if (e.key === "Escape") closeAuth(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [showAuth]);

  const submitPrompt = (event) => {
    event.preventDefault();
    onGuest();
  };

  const quickPrompts = ["Try on a dress", "Build my look", "Show full outfit"];

  return (
    <div className="mira-home">
      <header className="mira-dashboard-header">
        <div className="mira-dashboard-brand"><span className="mira-brand-dot" /> MIRA</div>
        <div className="mira-location"><span>⌖</span> Sahibganj <small>· 816101</small></div>
        <nav className="mira-dashboard-actions" aria-label="Account">
          <button type="button" className="mira-atelier-btn" onClick={() => setShowBrands(true)}>Atelier</button>
          <button type="button" className="mira-icon-btn" aria-label="Shopping bag" onClick={() => setShowAuth(true)}>▱</button>
          <button type="button" className="mira-avatar-btn" aria-label="Log in" onClick={() => setShowAuth(true)}>P</button>
        </nav>
      </header>

      <nav className="mira-category-nav" aria-label="Shop categories">
        {['Dresses', 'Tops', 'Bottoms', 'Bags', 'Shoes', 'Outerwear'].map((category, index) => (
          <button key={category} type="button" className={index === 0 ? 'is-active' : ''} onClick={onGuest}>{category}</button>
        ))}
        <span className="mira-category-spacer" />
        <button type="button" onClick={onGuest}>Filters</button>
        <button type="button" onClick={() => setShowBrands(true)}>Brands</button>
      </nav>

      <main className="mira-dashboard-main">
        <section className="mira-dashboard-grid" aria-label="Mira styling studio">
          <article className="mira-style-hero">
            <img src="/hero-home.jpg" alt="A woman relaxing in a cream outfit" />
            <div className="mira-style-hero-shade" />
            <div className="mira-style-hero-top"><span>MIRA</span><b>✦ Featured</b></div>
            <button type="button" className="mira-hero-arrow mira-hero-arrow--left" aria-label="Previous look" onClick={onGuest}>‹</button>
            <button type="button" className="mira-hero-arrow" aria-label="Next look" onClick={onGuest}>›</button>
            <div className="mira-style-hero-copy">
              <p>Today’s edit</p>
              <h1>Soft tailoring,<br />made personal.</h1>
              <button type="button" onClick={onGuest}>Explore the look <span>→</span></button>
            </div>
          </article>

          <article className="mira-tryon-card">
            <div className="mira-panel-heading"><div><span className="mira-panel-avatar">✦</span> Virtual try-on <em>Preview</em></div><button type="button" aria-label="Open try-on" onClick={onGuest}>↗</button></div>
            <div className="mira-tryon-preview"><img src="/hero-home-sm.jpg" alt="Virtual try-on preview" /><span className="mira-tryon-spark">✦</span></div>
            <div className="mira-tryon-copy"><h2>See it on you</h2><p>Upload a photo and discover your next favourite look.</p><button type="button" onClick={onGuest}>Start a try-on <span>→</span></button></div>
          </article>
        </section>

        <section className="mira-recommendations" aria-labelledby="mira-recommendations-title">
          <div className="mira-section-heading"><div><p>Curated for you</p><h2 id="mira-recommendations-title">Fresh looks to explore</h2></div><button type="button" onClick={onGuest}>See all <span>→</span></button></div>
          <div className="mira-look-row">
            {['The polished set', 'Weekend ease', 'A little after-dark', 'Finishing touches'].map((look, index) => (
              <button type="button" className={`mira-look-card mira-look-card--${index + 1}`} key={look} onClick={onGuest}>
                <span className="mira-look-card-image"><img src={index === 2 ? '/hero-home-sm.jpg' : '/hero-home.jpg'} alt="" /></span>
                <span><b>{look}</b><small>{['4 pieces', '5 pieces', '3 pieces', 'Accessories'][index]}</small></span>
              </button>
            ))}
          </div>
        </section>
      </main>

      <div className="mira-prompt-dock">
        <div className="mira-prompt-orb">✦</div>
        <div className="mira-prompt-chips">
          {quickPrompts.map((quickPrompt) => <button key={quickPrompt} type="button" onClick={onGuest}>{quickPrompt}</button>)}
        </div>
        <form className="mira-prompt-form" onSubmit={submitPrompt}>
          <input value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="Ask Mira anything — e.g. purple dresses" aria-label="Ask Mira anything" />
          <button type="submit">Send <span>→</span></button>
        </form>
      </div>

      {showAuth && (
        <div
          className="mira-home-auth"
          role="dialog"
          aria-modal="true"
          aria-label="Sign in"
          onClick={(e) => { if (e.target === e.currentTarget) closeAuth(); }}
        >
          <div className="mira-home-auth-panel">
            <button
              type="button"
              className="mira-home-auth-close"
              aria-label="Close"
              onClick={closeAuth}
            >
              ✕
            </button>
            <p className="mira-home-auth-eyebrow">✦ Mira</p>
            <h2 className="mira-home-auth-title">Sign in</h2>
            <p className="mira-home-auth-sub">
              Save picks, try-ons, and a stylist that remembers you.
            </p>
            <AuthButtons
              onGoogle={onGoogle}
              onFacebook={onFacebook}
              onGithub={onGithub}
              authError={authError}
            />
            <button className="login-guest-btn" onClick={onGuest}>
              Browse without signing in →
            </button>
            <p className="login-legal">
              By signing in you agree to our{" "}
              <a href="/privacy" target="_blank" rel="noopener noreferrer">Privacy Policy</a>.
              We never post on your behalf.
            </p>
          </div>
        </div>
      )}

      {showBrands && (
        <ForBrands
          onClose={() => setShowBrands(false)}
          onStartDemo={() => { setShowBrands(false); onGuest?.(); }}
        />
      )}
    </div>
  );
}

function GoogleIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#FFC107" d="M43.6 20H24v8h11.3C33.6 33.6 29.3 37 24 37c-7.2 0-13-5.8-13-13s5.8-13 13-13c3.1 0 6 1.1 8.2 3l5.7-5.7C34.5 5.1 29.5 3 24 3 12.4 3 3 12.4 3 24s9.4 21 21 21c11 0 20.4-8 20.4-21 0-1.3-.1-2.7-.4-4z"/>
      <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.6 15 19 12 24 12c3.1 0 6 1.1 8.2 3l5.7-5.7C34.5 5.1 29.5 3 24 3c-7.7 0-14.4 4.1-18.1 10.3-.4.7-.9 1.6-1.3 2.4z"/>
      <path fill="#4CAF50" d="M24 45c5.2 0 10.1-1.9 13.8-5.1l-6.4-5.4C29.4 36.4 26.8 37 24 37c-5.2 0-9.6-3.3-11.3-8H6.1C9.8 39.7 16.4 45 24 45z"/>
      <path fill="#1976D2" d="M43.6 20H24v8h11.3c-.9 2.5-2.5 4.7-4.6 6.3l6.4 5.4C40.8 36.2 44 30.6 44 24c0-1.3-.1-2.7-.4-4z"/>
    </svg>
  );
}

function FacebookIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#1877F2" d="M24 12.07C24 5.41 18.63 0 12 0S0 5.41 0 12.07C0 18.1 4.39 23.1 10.13 24v-8.44H7.08v-3.49h3.04V9.41c0-3.02 1.8-4.7 4.54-4.7 1.31 0 2.68.24 2.68.24v2.97h-1.51c-1.49 0-1.95.93-1.95 1.88v2.27h3.32l-.53 3.49h-2.79V24C19.61 23.1 24 18.1 24 12.07z"/>
    </svg>
  );
}

function GithubIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true">
      <path fill="currentColor" d="M12 0C5.37 0 0 5.37 0 12c0 5.3 3.44 9.8 8.21 11.39.6.11.82-.26.82-.58v-2.03c-3.34.73-4.04-1.61-4.04-1.61-.55-1.39-1.34-1.76-1.34-1.76-1.09-.74.08-.73.08-.73 1.2.08 1.84 1.24 1.84 1.24 1.07 1.83 2.81 1.3 3.5.99.11-.78.42-1.3.76-1.6-2.67-.3-5.47-1.33-5.47-5.93 0-1.31.47-2.38 1.24-3.22-.13-.3-.54-1.52.12-3.18 0 0 1.01-.32 3.3 1.23a11.5 11.5 0 0 1 3-.4c1.02 0 2.04.13 3 .4 2.28-1.55 3.29-1.23 3.29-1.23.66 1.66.25 2.88.12 3.18.77.84 1.24 1.91 1.24 3.22 0 4.61-2.81 5.63-5.48 5.92.43.37.81 1.1.81 2.22v3.29c0 .32.21.7.82.58C20.56 21.8 24 17.3 24 12c0-6.63-5.37-12-12-12z"/>
    </svg>
  );
}
