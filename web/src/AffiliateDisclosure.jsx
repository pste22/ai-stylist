/** ASCI-friendly affiliate disclosure — keep near buy CTAs. */
export default function AffiliateDisclosure({ compact = false }) {
  if (compact) {
    return (
      <p className="aff-disclose aff-disclose--compact">
        Mira may earn a commission — your price stays the same.
      </p>
    );
  }
  return (
    <p className="aff-disclose">
      <strong>Affiliate disclosure:</strong> When you shop via Mira, we may earn a small
      commission from the retailer. It never changes the price you pay.
    </p>
  );
}
