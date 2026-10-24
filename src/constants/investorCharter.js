// Investor Charter for Investment Advisers, verbatim from Annexure A of SEBI circular
// SEBI/HO/MIRSD/MIRSD-PoD/P/CIR/2025/80 dated 02-06-2025. If SEBI revises it, replace the text
// here and update CHARTER_SOURCE. Items are strings; nested lists are { text, sub: [...] }.

export const CHARTER_SOURCE = {
  circular: "SEBI/HO/MIRSD/MIRSD-PoD/P/CIR/2025/80",
  date: "2 June 2025",
  url: "https://www.sebi.gov.in/sebi_data/attachdocs/jun-2025/1748863758785.pdf",
};

export const IA_LIST_URL = "https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doRecognisedFpi=yes&intmId=13";

export const CHARTER = [
  {
    title: "A. Vision and Mission Statements for investors",
    items: [
      { text: "Vision", sub: ["Invest with knowledge & safety."] },
      { text: "Mission", sub: ["Every investor should be able to invest in right investment products based on their needs, manage and monitor them to meet their goals, access reports and enjoy financial wellness."] },
    ],
  },
  {
    title: "B. Details of business transacted by the Investment Adviser with respect to the investors",
    items: [
      "To enter into an agreement with the client providing all details including fee details, aspects of Conflict of interest disclosure and maintaining confidentiality of information.",
      "To do a proper and unbiased risk – profiling and suitability assessment of the client.",
      "To conduct audit annually.",
      "To disclose the status of complaints on its website.",
      "To disclose the name, proprietor name, type of registration, registration number, validity, complete address with telephone numbers and associated SEBI Office details (i.e. Head office/ regional/ local Office) on its website.",
      "To employ only qualified and certified employees.",
      "To deal with clients only from official number",
      "To maintain records of interactions, with all clients including prospective clients (prior to onboarding), where any conversation related to advice has taken place.",
      "To ensure that all advertisements are in adherence to the provisions of the Advertisement Code for Investment Advisers",
      "Not to discriminate in terms of services provided, among clients opting for same/similar products/services offered by investment adviser.",
    ],
  },
  {
    title: "C. Details of services provided to investors (No Indicative Timelines)",
    items: [
      { text: "Onboarding of Clients", sub: ["Sharing of agreement copy", "Completing KYC of clients"] },
      {
        text: "Disclosure to Clients",
        sub: [
          "To provide full disclosure about its business, affiliations, compensation in the agreement.",
          "To not access client’s accounts or holdings for offering advice.",
          "To disclose the risk profile to the client.",
          "To disclose any conflict of interest of the investment advisory activities with any other activities of the investment adviser.",
          "To disclose the extent of use of Artificial Intelligence tools in providing investment advisory services.",
        ],
      },
      "To provide investment advice to the client based on the risk-profiling of the clients and suitability of the client.",
      "To treat all advisory clients with honesty and integrity.",
      "To make adequate disclosure to the investor of all material facts such as risks, obligations, costs, etc. relating to the products or securities advised by the adviser.",
      "To provide clear guidance and adequate caution notice to clients when providing investment advice for dealing in complex and high-risk financial products/services.",
      "To ensure confidentiality of information shared by clients unless such information is required to be provided in furtherance of discharging legal obligations or a client has provided specific consent to share such information.",
      "To disclose the timelines for the various services provided by the investment adviser to clients and ensure adherence to the said timelines.",
    ],
  },
  {
    title: "D. Details of grievance redressal mechanism and how to access it",
    items: [
      {
        text: "1. Investor can lodge complaint/grievance against Investment Adviser in the following ways:",
        sub: [
          "Mode of filing the complaint with investment adviser: In case of any grievance / complaint, an investor may approach the concerned Investment Adviser who shall strive to redress the grievance immediately, but not later than 21 days of the receipt of the grievance.",
          "Mode of filing the complaint on SCORES or with Investment Adviser Administration and Supervisory Body (IAASB): i. SCORES 2.0 (a web based centralized grievance redressal system of SEBI for facilitating effective grievance redressal in time-bound manner) (https://scores.sebi.gov.in). Two level review for complaint/grievance against investment adviser: First review done by designated body (IAASB); Second review done by SEBI. ii. Email to designated email ID of IAASB",
        ],
      },
      "2. If the Investor is not satisfied with the resolution provided by the Market Participants, then the Investor has the option to file the complaint/ grievance on SMARTODR platform for its resolution through online conciliation or arbitration.",
      "3. With regard to physical complaints, investors may send their complaints to: Office of Investor Assistance and Education, Securities and Exchange Board of India, SEBI Bhavan, Plot No. C4-A, ‘G’ Block, Bandra-Kurla Complex, Bandra (E), Mumbai - 400 051",
    ],
  },
  {
    title: "E. Rights of investors",
    items: [
      "Right to Privacy and Confidentiality",
      "Right to Transparent Practices",
      "Right to fair and Equitable Treatment",
      "Right to Adequate Information",
      { text: "Right to Initial and Continuing Disclosure", sub: ["Right to receive information about all the statutory and regulatory disclosures."] },
      "Right to Fair & True Advertisement",
      { text: "Right to Awareness about Service Parameters and Turnaround Times", sub: ["Right to be informed of the timelines for each service"] },
      { text: "Right to be Heard and Satisfactory Grievance Redressal", sub: ["Right to have timely redressal"] },
      "Right to Suitability of the Financial Products",
      "Right to Exit from Financial product or service in accordance with the terms of agreement with the investment adviser",
      "Right to receive clear guidance and caution notice when dealing in Complex and High-Risk Financial Products and Services",
      { text: "Additional Rights to vulnerable consumers", sub: ["Right to get access to services in a suitable manner even if differently abled"] },
      "Right to provide feedback on the financial products and services used",
      "Right against coercive, unfair, and one-sided clauses in financial agreements",
    ],
  },
  {
    title: "F. Expectations from the investors (Responsibilities of investors)",
    items: [
      {
        text: "Do’s",
        ordered: true,
        sub: [
          "Always deal with SEBI registered Investment Advisers.",
          "Ensure that the Investment Adviser has a valid registration certificate.",
          "Check for SEBI registration number. Please refer to the list of all SEBI registered Investment Advisers which is available on SEBI website in the following link: (link below)",
          "Pay only advisory fees to your Investment Adviser. Make payments of advisory fees through banking channels only and maintain duly signed receipts mentioning the details of your payments. You may make payment of advisory fees through Centralised Fee Collection Mechanism (CeFCoM) of IAASB if investment adviser has opted for the mechanism.",
          "Always ask for your risk profiling before accepting investment advice. Insist that Investment Adviser provides advisory strictly on the basis of your risk profiling and take into account available investment alternatives.",
          "Ask all relevant questions and clear your doubts with your Investment Adviser before acting on advice.",
          "Assess the risk–return profile of the investment as well as the liquidity and safety aspects before making investments.",
          "Insist on getting the terms and conditions in writing duly signed and stamped. Read these terms and conditions carefully particularly regarding advisory fees, advisory plans, category of recommendations etc. before dealing with any Investment Adviser.",
          "Be vigilant in your transactions.",
          "Approach the appropriate authorities for redressal of your doubts / grievances.",
          "Inform SEBI about Investment Advisers offering assured or guaranteed returns.",
          "Always be aware that you have the right to exit the service of an Investment Adviser",
          "Always be aware that you have the right to seek clarifications and clear guidance on advice",
          "Always be aware that you have the right to provide feedback to the Investment Adviser in respect of services received.",
          "Always be aware that you will not be bound by any clause, prescribed by the investment adviser, which is contravening any regulatory provisions.",
        ],
      },
      {
        text: "Don’ts",
        ordered: true,
        sub: [
          "Don’t fall for stock tips offered under the pretext of investment advice.",
          "Do not provide funds for investment to the Investment Adviser.",
          "Don’t fall for the promise of indicative or exorbitant or assured returns by the Investment Advisers. Don’t let greed overcome rational investment decisions.",
          "Don’t fall prey to luring advertisements or market rumors.",
          "Avoid doing transactions only on the basis of phone calls or messages from any Investment adviser or its representatives.",
          "Don’t take decisions just because of repeated messages and calls by Investment Advisers.",
          "Do not fall prey to limited period discount or other incentive, gifts, etc. offered by Investment advisers.",
          "Don’t rush into making investments that do not match your risk taking appetite and investment goals.",
          "Do not share login credential and password of your trading, demat or bank accounts with the Investment Adviser.",
        ],
      },
    ],
  },
];
