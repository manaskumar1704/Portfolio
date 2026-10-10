"use client";

/**
 * What happens to a visitor's words, stated before they type them.
 *
 * This is plain text next to the composer on purpose, not a link and not a
 * footnote in the answer. It describes what happens *before* the model sees the
 * message, which is a different question from how the answer is formatted.
 * Burying it in the formatting would defeat it.
 *
 * The third-party-provider line is the one that most often goes unstated and is
 * the one a recruiter with a data-protection obligation needs. The API sends
 * the question to Google's Gemini API, which is a transfer of the visitor's
 * words to a third party. It is not optional here: the agent cannot answer
 * without it.
 *
 * "up to a day" is Google's stated retention for free-tier API payloads. It is
 * their policy, not ours, so it is stated as what they say rather than as a
 * promise we control.
 */

export function PrivacyNote() {
  return (
    <details className="privacy">
      <summary className="privacy-summary">Before you write to him</summary>

      <div className="privacy-body">
        <p>
          Your message is <strong>not sent</strong> when you write it. It is saved as a
          draft, and an approve button appears here. Nothing reaches his inbox until you
          press it.
        </p>

        <p>
          Your IP address is stored only as a salted one-way hash, so that the approve
          button cannot be pressed from a different network than the one that wrote the
          message. That hash is deleted the moment the message is sent. The address itself
          is never written down.
        </p>

        <p>
          The draft is deleted if you do not approve it within 7 days. A sent message keeps
          its text for 30 days, then is deleted too.
        </p>

        <p>
          <strong>
            Questions you ask the agent are sent to Google&apos;s Gemini API, a
            third-party provider, which may retain them for up to a day. Messages you
            write are held on this site&apos;s server until you approve them.
          </strong>{" "}
          The model answers using only the portfolio documents listed as citations.
        </p>
      </div>
    </details>
  );
}