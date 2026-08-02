export default function PrivacyPolicy({ onClose }) {
  return (
    <div className="privacy-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="privacy-modal">
        <h2>Privacy Policy</h2>
        <p>Last updated: July 2026. Mira AI Stylist is operated by its founders and complies with India's Digital Personal Data Protection Act 2023 (DPDP Act).</p>

        <h3>What we collect</h3>
        <ul>
          <li><strong>Identity</strong>: Your name, email address, and profile picture from the OAuth provider you sign in with (Google or GitHub).</li>
          <li><strong>Style preferences</strong>: Answers you give during onboarding (style vibe, budget, sizes). Stored in our database against your user ID.</li>
          <li><strong>Product interactions</strong>: Which products you save, like, or click "Buy" on. Used to personalise recommendations.</li>
          <li><strong>Conversation context</strong>: A short summary of your sessions is stored to help Mira remember your preferences across visits. Raw audio is never stored.</li>
          <li><strong>Pinterest data</strong> (if connected): Board and pin images are analysed for style signals. We store only the derived summary, not your raw Pinterest data.</li>
        </ul>

        <h3>How we use it</h3>
        <ul>
          <li>To personalise Mira's recommendations to your taste, budget, and size.</li>
          <li>To send session summary emails and (for Pro subscribers) weekly First Look emails, if you opt in.</li>
          <li>To measure which products drive the most value so we can improve our catalog.</li>
          <li>We do not sell your data to third parties. Ever.</li>
        </ul>

        <h3>Third-party services</h3>
        <ul>
          <li><strong>Google Gemini</strong>: Your voice/text input is sent to Google's Gemini Live API to generate Mira's responses. Governed by Google's API data policy.</li>
          <li><strong>Supabase</strong>: Our database and authentication provider. Data stored in the EU (Frankfurt region).</li>
          <li><strong>Resend</strong>: Used to send transactional emails. Only your email address is shared.</li>
          <li><strong>Affiliate networks</strong> (Myntra, Ajio, Amazon): When you click "Buy →", you are redirected to these retailers. We earn a commission. They have their own privacy policies.</li>
        </ul>

        <h3>Data retention</h3>
        <p>Your data is retained while your account is active. You can delete your account and all associated data at any time from your account settings. Deletion is permanent and irreversible within 30 days.</p>

        <h3>Your rights (DPDP Act 2023)</h3>
        <ul>
          <li>Right to access: Request a copy of your data by emailing us.</li>
          <li>Right to correction: Update your preferences at any time in the app.</li>
          <li>Right to erasure: Delete your account from the account menu — all data is removed immediately.</li>
          <li>Right to grievance redressal: Contact us at the email below.</li>
        </ul>

        <h3>Contact</h3>
        <p>For privacy questions or data requests: <strong>privacy@mira.style</strong> (placeholder — update before launch).</p>

        <button className="privacy-close" onClick={onClose}>Close</button>
      </div>
    </div>
  );
}
