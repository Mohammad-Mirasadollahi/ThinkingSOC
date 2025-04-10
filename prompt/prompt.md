# SOC Tier 1 Splunk Alert Analysis — Standardized Threat Investigation

This prompt assists SOC Tier 1 analysts in systematically analyzing Splunk alerts, accurately extracting relevant fields from provided data, and clearly summarizing findings in a consistent, unified JSON structure.

---

{
  "OverallRiskScore": 85,
  "ThreatStatus": "Potential Threat",
  "ThreatSummary": "Brief Description of all the ThreatStatus",
  "MITREMapping": {
    "MappedTechniques": [
      {
        "TechniqueID": "TXXXX",
        "Description": "Description if applicable"
      }
    ]
  },
  "Indicators": [
    {
      "ID": 1,
      "Title": "Descriptive Title of Indicator",
      "Reason": "Clearly state the reason the indicator is suspicious.",
      "Evidence": ["Relevant evidence from alert fields"]
    },
    {
      "ID": 2,
      "Title": "Another Indicator Title",
      "Reason": "Clearly state the reason.",
      "Evidence": ["Additional supporting details"]
    }
    // Continue adding new Indicators objects in the same format (ID: 1, ID: 2, etc.) if more IOCs are discovered
  ],
  "InvestigationDetails": [
    {
      "Step": "Corroborating Evidence",
      "Reason": "Provide supporting details from alert data or historical records."
    },
    {
      "Step": "Anomaly Explanation",
      "Reason": "Explain clearly why the behavior or data observed is abnormal."
    },
    {
      "Step": "Comparison with Known Threats",
      "Reason": "Describe briefly how observed behavior aligns with known threats or previous incidents."
    },
    {
      "Step": "Final Conclusion",
      "Reason": "Clearly state the final determination (False Positive or Potential Threat or Confirmed Malicious)."
    }
  ],
  "DecisionTree": "Brief textual representation summarizing the logic behind the conclusion.",
  "Escalation": {
    "Reason": "Clearly justify why escalation is necessary, or set to null if not escalated."
  },
  "Conclusion": "Summarize the overall findings and recommend actionable next steps clearly."
}


---

## Usage Guidelines

- Gather and analyze all relevant alert data:
  - **Corroborate evidence** from alert fields or related sources.
  - **Explain anomalies** clearly, detailing why they deviate from normal activity.
  - **Compare with known threats** to see if any patterns match documented TTPs.
  - **Determine a final verdict** on whether the activity is malicious or benign.

- **Populate all required keys** in the JSON output, ensuring each field follows the Unified JSON specification (OverallRiskScore, ThreatStatus, ThreatSummary, etc.).

- **Escalation:** State **YES** or **NO**. Provide justification if necessary.

- **Multiple indicators:** If you have more than one reason or IOC, list them all under the `"Indicators"` array format. If new IOCs appear, add them in the same structure.

- **No assumptions** about mandatory checks (IPs, hashes, etc.). Base conclusions solely on the provided data.

- **IOC searches**: Look for IOCs up to three times. Stop after the third attempt, even if you suspect more.

- **Include explanations** (if any) directly in the JSON.

- **All outputs must be in JSON format** with no additional text or deviations.

ThreatStatus must be explicitly as one of:
- **False Positive**
- **Potential Threat**
- **Confirmed Malicious**
