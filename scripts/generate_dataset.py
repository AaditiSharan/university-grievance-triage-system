"""
generate_dataset.py
-------------------
Builds the SYNTHETIC grievance dataset for the LPU-GRIEVANCE-01 project.

Run from the project root:   python scripts/generate_dataset.py

Outputs
  config/category_tree.json          label space (master > category > subcategory) + routes
  config/routing_table.yaml          subcategory -> department
  data/synthetic/grievances_full.csv every record
  data/synthetic/incidents.csv       known-issue records for the incident clusters
  data/processed/train.csv, val.csv  training / validation split
  data/test_set/test.csv             held-out test split (never train on this)

Design notes
  * Every subcategory has 8 text templates (English + Hinglish). Templates whose
    index % 4 == 3 are HELD OUT: they only ever appear in the test set, so the
    test set contains wordings the model never saw in training.
  * Two whole incident clusters (C03, C06) are also held out for testing the matcher.
  * NOTHING here is real student data. The category tree is a PLACEHOLDER:
    replace it with the real RMS dropdown values when you have them.
"""
import json
import random
import re
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yaml

SEED = 42
rng = random.Random(SEED)
ROOT = Path(__file__).resolve().parent.parent

# ----------------------------------------------------------------------------
# 1. CATEGORY TREE + TEMPLATES
#    "~" at the start of a template marks it as Hinglish.
#    Slots in {braces} are filled randomly (see fresh_slots).
# ----------------------------------------------------------------------------
# name -> (master, category, subcategory, route, sensitivity_type, templates)
SUBS = {}


def S(master, cat, sub, route, templates, sens="NONE"):
    assert len(templates) == 8, sub
    SUBS[sub] = dict(master=master, category=cat, sub=sub, route=route,
                     sens=sens, templates=templates, code=f"T{len(SUBS) + 1:02d}")


# ---- Academics ----
S("Academics", "Timetable", "Section Timetable Not Updated", "Academic Operations", [
    "Timetable for section {section} is not updated on UMS. We do not know which classes are scheduled.",
    "Our section {section} timetable has not been uploaded even after the term has started.",
    "~{section} ka timetable abhi tak update nahi hua hai, kaunsi class kab hai pata nahi chal raha.",
    "No timetable is visible for {section}. Students are missing classes because of this.",
    "Sir, the timetable of {section} is still blank on the portal. Kindly upload it.",
    "~UMS pe hamare section {section} ka time table nahi dikh raha, please update karwa dijiye.",
    "Classes for {section} are happening randomly because the official timetable has not been published.",
    "~Section {section} ka schedule portal pe missing hai, kab tak aayega?"])
S("Academics", "Timetable", "Class Clash", "Academic Operations", [
    "Two of my courses, {course} and {course2}, are scheduled at the same time on {day}.",
    "There is a clash between the {course} lecture and the {course2} lab in my timetable on {day}.",
    "~{course} aur {course2} ki class ek hi time pe hai {day} ko, kya karu?",
    "I cannot attend both {course} and {course2} as the slots overlap on {day}. Please fix the clash.",
    "Timetable shows overlapping slots for {course} and {course2}. Requesting a change of slot.",
    "~Mere timetable mein {day} ko do subjects clash kar rahe hain, please slot change kijiye.",
    "My lab for {course} overlaps with a theory class of {course2} every {day}.",
    "~{day} ko {course} ka lab aur {course2} ki lecture same time pe aa rahe hain."])
S("Academics", "Attendance", "Attendance Not Updated", "Academic Operations", [
    "My attendance for {course} is not updated on UMS even though I attended all classes this week.",
    "Attendance of {course} is showing less than actual. Please correct it.",
    "~{course} ki attendance UMS pe galat lag rahi hai, maine saari classes attend ki hain.",
    "Faculty has not uploaded my attendance for {course} for the last two weeks.",
    "I was present in the {course} class on {date} but it is marked absent.",
    "~Meri attendance update nahi hui hai {course} mein, please check karwa dijiye.",
    "Attendance for lab sessions of {course} is missing from my record.",
    "~{date} ki {course} ki attendance absent dikha rahi hai jabki main class mein tha."])
S("Academics", "Attendance", "Attendance Shortage Condonation", "Academic Operations", [
    "My attendance in {course} is below 75 percent due to illness. I request condonation.",
    "Please let me know the process to apply for attendance condonation for {course}.",
    "~Meri attendance {course} mein kam hai, kya condonation mil sakta hai?",
    "I have a shortage of attendance in two courses and want to appeal so that I am allowed to sit in the exam.",
    "Requesting relaxation in attendance for {course} because I represented the university in an event.",
    "~Attendance shortage ka form kahan se bharna hai, {course} mein 70 percent hai.",
    "Is condonation of attendance allowed this term? My attendance is 68 percent in {course}.",
    "~Condonation ke liye kya documents lagte hain? Meri attendance kam hai."])
S("Academics", "Course Registration", "Elective Change Request", "Academic Operations", [
    "I want to change my elective from {course} to {course2}. How can I do this?",
    "The elective change window has closed but I did not get my chosen course {course2}. Please help.",
    "~Mujhe {course} ki jagah {course2} elective lena hai, kya process hai?",
    "Course {course2} shows no seats available. Requesting a seat in this elective.",
    "I was allotted the wrong elective in course registration. Kindly change it to {course2}.",
    "~Course registration mein galat elective aa gaya hai, please change kar dijiye.",
    "Requesting permission to swap {course} with {course2} as the timings suit me better.",
    "~{course2} mein seat nahi mil rahi, kya registration dobara open hoga?"])
S("Academics", "Online Classes", "Online Class Link Issue", "Academic Operations", [
    "The online class link for {course} is not working. We could not join today's lecture.",
    "No meeting link was shared for the {course} online class on {day}.",
    "~{course} ki online class ka link kaam nahi kar raha, join nahi ho pa raha.",
    "Recorded lectures for {course} are not available on the portal even after one week.",
    "The online session of {course} keeps disconnecting and the faculty cannot be heard.",
    "~{course} ki recording portal pe nahi aayi hai, please upload karwayein.",
    "I get an access denied error when I open the {course} class link.",
    "~Online class ka link expire ho gaya hai {course} ka, naya bhejiye."])

# ---- Examination ----
S("Examination", "Results", "Result Not Declared", "Examination Cell", [
    "The result of {course} has not been declared yet even though the exam was a month ago.",
    "My result for {course} is not showing on UMS.",
    "~{course} ka result abhi tak declare nahi hua hai, kab aayega?",
    "Result is still pending for the last term examination of {course}. Please update the date.",
    "When will the {course} results be published? We have been waiting for weeks.",
    "~UMS pe result nahi dikh raha {course} ka, please check kijiye.",
    "Marks for {course} are not uploaded and the result status shows pending.",
    "~Result kab tak aayega {course} ka? Backlog form bharna hai."])
S("Examination", "Results", "Marks Mismatch", "Examination Cell", [
    "My marks in {course} on UMS are different from what was shown on my answer sheet.",
    "There is a mismatch in my internal marks for {course}. The faculty told me a higher score.",
    "~{course} mein mere marks galat chadhe hain, answer sheet mein zyada the.",
    "Total marks in {course} do not add up correctly on my result card.",
    "I scored full marks in the {course} quiz but it is recorded as zero in the portal.",
    "~Result card mein {course} ke marks kam dikha rahe hain, please sudhaar kijiye.",
    "My CA marks for {course} are missing from the final total.",
    "~{course} ke internal marks galat hain, kaun correct karega?"])
S("Examination", "Re-evaluation", "Re-evaluation Request", "Examination Cell", [
    "I want to apply for re-evaluation of {course} because the marks are much lower than expected.",
    "What is the last date and fee for revaluation of the {course} paper?",
    "~{course} ka re-evaluation karwana hai, form kahan se milega?",
    "Please allow me to see my answer script of {course} and apply for re-checking.",
    "The re-evaluation link is not opening for {course}. Kindly extend the date.",
    "~Revaluation ki last date kya hai? {course} mein fail ho gaya hoon.",
    "I applied for re-evaluation of {course} but there has been no update after two weeks.",
    "~Re-evaluation ka status kab pata chalega {course} ka?"])
S("Examination", "Admit Card", "Admit Card Not Generated", "Examination Cell", [
    "My admit card is not getting generated on UMS for the upcoming exams.",
    "Admit card shows a 'fee pending' error though I have already paid the fee.",
    "~Admit card download nahi ho raha, error aa raha hai.",
    "I am unable to download the hall ticket for {course}. The exam is close.",
    "The admit card has my photo missing and a wrong course list. Please correct it.",
    "~Mera admit card generate nahi hua hai, exam aa rahe hain, please jaldi kijiye.",
    "Admit card option is not visible in my login even though other students can see it.",
    "~Hall ticket pe galat naam aa gaya hai, kaise theek hoga?"])
S("Examination", "Datesheet", "Exam Schedule Concern", "Examination Cell", [
    "The exams of {course} and {course2} are on consecutive days, please reschedule one.",
    "We request a gap of at least one day between the {course} and {course2} papers.",
    "~Datesheet mein do exam ek hi din pe aa gaye hain, please dekhiye.",
    "The datesheet has the {course} exam on a festival day. Kindly reconsider the date.",
    "Two papers on the same day is too tiring, requesting a change in the datesheet.",
    "~Exam ki date {course} ke liye clash kar rahi hai {course2} ke saath.",
    "Datesheet for the term has not been released yet, we need time to prepare.",
    "~Exam ke beech mein gap nahi hai, preparation ke liye time chahiye."])

# ---- Finance ----
S("Finance", "Fee", "Fee Payment Not Reflected", "Accounts Office", [
    "I paid the fee of Rs {amount} on {paydate} but it is not reflecting in my account.",
    "Money was deducted from my bank for the fee payment but UMS still shows it as pending.",
    "~Fees ka payment kar diya {paydate} ko par UMS pe reflect nahi ho raha.",
    "The payment gateway failed after deduction of Rs {amount}. The transaction is not visible on the portal.",
    "I paid the hostel fee of Rs {amount} twice by mistake and want the extra amount back.",
    "~Paisa kat gaya hai fees ka lekin receipt nahi mili, please check karein.",
    "Fee status is showing due even after payment through net banking on {paydate}.",
    "~Maine Rs {amount} ka payment kiya tha par balance wahi dikha raha hai."])
S("Finance", "Fee", "Fee Receipt Request", "Accounts Office", [
    "I need a fee receipt for the previous term for my education loan documents.",
    "Please provide the fee payment receipt for Rs {amount}, I am unable to download it.",
    "~Fees ki receipt chahiye bank loan ke liye, kahan se milegi?",
    "Where can I download the fee receipt for the current semester?",
    "The fee receipt shows a wrong name. Please issue a corrected receipt.",
    "~Fee receipt download nahi ho rahi, error aa raha hai.",
    "I want the consolidated fee statement of all terms for scholarship purposes.",
    "~Pichhle semester ki fees receipt kaise nikalun?"])
S("Finance", "Fee", "Fee Concession Request", "Accounts Office", [
    "My father lost his job and I request a fee concession for this term.",
    "Please tell me the procedure to apply for a fee waiver based on financial hardship.",
    "~Fees bahut zyada hai, kya installment ya concession mil sakta hai?",
    "I want to extend the last date of fee submission as the loan amount is delayed.",
    "Is there any concession for students who scored above 90 percent in the previous term?",
    "~Papa ki income kam hai, fees mein relaxation chahiye.",
    "Can the fee of Rs {amount} be paid in two instalments?",
    "~Fee deposit ki date badhaayi ja sakti hai kya? loan abhi nahi aaya."])
S("Finance", "Scholarship", "Scholarship Not Credited", "Scholarship Cell", [
    "My scholarship amount for the last term has not been credited yet.",
    "I was awarded a merit scholarship but it is not adjusted in my fee account.",
    "~Scholarship ka paisa abhi tak nahi aaya, please status batayein.",
    "The scholarship status on UMS has been pending for two months. Please check.",
    "Scholarship of Rs {amount} was promised but is not reflected in my fee statement.",
    "~Meri scholarship fee mein adjust nahi hui hai, please dekhiye.",
    "My government scholarship documents are verified but the amount is not released.",
    "~Scholarship ka status approved dikha raha hai par amount nahi mila."])

# ---- Hostel ----
S("Hostel", "Maintenance", "Room Maintenance", "Hostel Administration", [
    "The fan in my room {room} is not working for the last four days. Please repair it.",
    "There is a water leakage in the bathroom of room {room}.",
    "~Room {room} mein light kharab hai, kai din se complaint kar rahe hain.",
    "The room heater is not working and it is very cold at night in {block}.",
    "Water supply on our floor in {block} has been irregular and there is no hot water.",
    "~Mere room ka AC kaam nahi kar raha, maintenance wale nahi aa rahe.",
    "The lock of my room door in {block} is broken. Please get it fixed.",
    "~{block} mein lift kharab hai, upar jaane mein dikkat hai."])
S("Hostel", "Mess", "Mess Food Quality", "Hostel Administration", [
    "The food quality in the mess of {block} has been very poor this week.",
    "We found insects in the dal served at the mess today. Please take action.",
    "~Mess ka khana bahut kharab hai, roz ek hi sabzi mil rahi hai.",
    "Mess timings are too short and the food gets over before many students reach.",
    "The mess does not offer enough vegetarian options during dinner.",
    "~Mess mein safai nahi hai aur khana thanda milta hai.",
    "Drinking water in the mess is not clean in {block}.",
    "~Mess ke menu mein badlav chahiye, same cheez bar bar aati hai."])

# ---- IT Services ----
S("IT Services", "Network", "Wi-Fi Not Working", "IT Services", [
    "The Wi-Fi in {block} is not working since morning. We cannot attend online classes.",
    "Internet speed in {block} is extremely slow and keeps disconnecting.",
    "~{block} mein wifi kaam nahi kar raha, kal se net band hai.",
    "Unable to connect to campus Wi-Fi, it says authentication failed.",
    "No internet in the hostel block {block} for two days. Please fix it urgently.",
    "~{block} mein wifi ka signal bilkul nahi aa raha.",
    "The Wi-Fi router on the second floor of {block} seems to be down.",
    "~Campus wifi connect nahi ho raha, baar baar login maang raha hai."])
S("IT Services", "UMS", "UMS Login Issue", "IT Services", [
    "I am unable to log in to UMS. It says invalid password even after resetting.",
    "My UMS account got locked after multiple attempts. Please unlock it.",
    "~UMS mein login nahi ho raha, OTP nahi aa raha.",
    "I did not receive the OTP on my registered mobile number for UMS login.",
    "UMS shows 'user not found' for my registration number.",
    "~Password reset ka link kaam nahi kar raha UMS pe.",
    "My UMS profile is showing another student's course list. Please check.",
    "~UMS open hi nahi ho raha, page error aa raha hai."])

# ---- Administration ----
S("Administration", "Documents", "Bonafide Certificate Request", "Registrar Office", [
    "I need a bonafide certificate for my passport application. How can I apply?",
    "Please issue a bonafide certificate for the bank, it has been pending for a week.",
    "~Bonafide certificate chahiye scholarship ke liye, kahan apply karun?",
    "I have applied for a character certificate but it has not been issued yet.",
    "I need a transcript and degree verification letter for higher studies.",
    "~Bonafide ka status kya hai? Do hafte ho gaye.",
    "Where should I collect my migration certificate from?",
    "~Certificate ke liye fees kitni lagti hai aur kitne din mein milega?"])
S("Administration", "Documents", "ID Card Issue", "Registrar Office", [
    "I lost my ID card and need a duplicate. What is the process?",
    "My ID card is not working at the library and the hostel gate scanner.",
    "~ID card abhi tak nahi mila, admission ko do mahine ho gaye.",
    "My ID card has the wrong photo and wrong registration number.",
    "The ID card was damaged and I would like to get a new one issued.",
    "~Mera ID card kho gaya hai, duplicate kaise banwaun?",
    "Why has the ID card not been distributed to our batch yet?",
    "~ID card ka barcode scan nahi ho raha, library mein dikkat aati hai."])
S("Administration", "Transport", "Bus Route or Timing", "Transport Office", [
    "The college bus on the Jalandhar route is always late and overcrowded.",
    "Please add a bus stop near the railway station for students living nearby.",
    "~Bus ka time badal diya gaya hai par kisi ne bataya nahi.",
    "No seat is available in the bus even after paying the transport fee.",
    "I want to change my transport route from Phagwara to Ludhiana. How do I apply?",
    "~Bus bahut der se aati hai, class miss ho jaati hai.",
    "Transport fee has been charged but the bus pass has not been issued.",
    "~Naye bus route ka schedule kahan milega?"])
S("Administration", "Library", "Library Book or Access Issue", "Library", [
    "I am unable to issue books from the library as my account shows a fine of Rs {amount2}.",
    "The e-resources and journal access are not working from the hostel network.",
    "~Library mein book issue nahi ho rahi, system mein error dikha raha hai.",
    "The library timings should be extended during exams. Is that possible?",
    "I returned the book last month but it still shows as issued against my name.",
    "~Library ka fine galat lag gaya hai, please hatwa dijiye.",
    "Textbooks for {course} are not available in the library.",
    "~Library ka card activate nahi hua hai abhi tak."])

# ---- Events & Activities ----
S("Events & Activities", "Duty Leave", "Event DL Not Updated", "Student Activities (SDMA)", [
    "I participated in {event} but the duty leave is not updated in my attendance.",
    "DL for {event} has not been applied yet. My attendance is falling because of this.",
    "~{event} ka DL abhi tak update nahi hua hai, attendance kat rahi hai.",
    "When will the duty leave for {event} be updated? It has been more than a week.",
    "Our team volunteered at {event} and still no DL has been given.",
    "~{event} ke liye DL kab tak lagega? Faculty attendance absent maan rahe hain.",
    "Duty leave of {event} is missing from UMS. Please update it for all participants.",
    "~SDMA ne {event} ka DL upload nahi kiya, please check karein."])
S("Events & Activities", "Events", "Event Registration Query", "Student Activities (SDMA)", [
    "How can I register for {event}? The registration link is not available.",
    "What is the last date to register for {event} and is there any fee?",
    "~{event} ke liye registration kahan se hoga?",
    "Can first year students take part in {event}?",
    "I paid for {event} registration but did not get a confirmation mail.",
    "~{event} mein team banane ki limit kitni hai?",
    "Please share the schedule and venue of {event}.",
    "~{event} ka certificate kab milega?"])

# ---- Student Welfare (SENSITIVE) ----
S("Student Welfare", "Ragging", "Ragging Complaint", "Anti-Ragging Cell", [
    "Seniors in {block} are forcing first year students to do things at night and threatening us if we complain. This is ragging.",
    "Some seniors made me stand and sing in the corridor and took my phone when I refused. Please act on this ragging.",
    "I am being ragged by seniors every night in the hostel, they abuse us and make us do their work.",
    "~Seniors ne hostel mein raat ko hume bulaya aur ragging ki, mana karne par dhamki di.",
    "First year students are being bullied and humiliated by seniors near {block}. We are scared to report this openly.",
    "Please keep my name confidential. A group of seniors is ragging us and demanding money.",
    "~ragging ho rahi hai {block} mein, seniors force karte hain, please help.",
    "Seniors are harassing juniors in the mess for introductions and hitting those who refuse."],
  sens="SAFETY")
S("Student Welfare", "Harassment", "Harassment Complaint", "Internal Complaints Committee", [
    "A faculty member keeps sending me inappropriate messages late at night and I feel unsafe.",
    "A student in my class is stalking me and following me after class. I do not feel safe on campus.",
    "I am being harassed by a classmate who keeps commenting on my body and sending obscene messages.",
    "~Ek ladka mujhe roz message karke pareshan kar raha hai aur mana karne par dhamki deta hai.",
    "Someone touched me inappropriately in the bus and I want to file a complaint.",
    "I am facing sexual harassment from a senior and I am afraid to tell anyone.",
    "My lab instructor passes personal comments and makes me uncomfortable. I want to report this confidentially.",
    "~Please help, ek vyakti meri photos ke naam pe mujhe blackmail kar raha hai."],
  sens="SAFETY")
S("Student Welfare", "Threat or Violence", "Threat or Violence Report", "Security & Student Welfare", [
    "Some students attacked my roommate near {block} last night and threatened to beat us.",
    "There was a fight in the hostel and a student has been threatened with a knife.",
    "A group of students is threatening me to give them money or they will hurt me.",
    "~Hostel mein ladai hui aur kuch log mujhe maarne ki dhamki de rahe hain.",
    "I received threatening messages from a senior saying he will harm me if I complain about him.",
    "A student brought a weapon to {block} and is threatening others. Please act immediately.",
    "~Kuch log {block} ke bahar mujhe maarne ki dhamki de rahe hain, mujhe darr lag raha hai.",
    "My roommate physically assaulted me last night and says he will do it again."],
  sens="SAFETY")
S("Student Welfare", "Mental Health", "Mental Health Concern", "Counselling Centre", [
    "I feel very depressed and cannot focus on anything. Sometimes I think there is no point in living.",
    "I have been having thoughts of ending my life because of academic pressure. I need someone to talk to.",
    "I cannot take this anymore, I want to give up everything. Please help me.",
    "~Mujhe bahut depression ho raha hai aur kabhi kabhi lagta hai ki mar jaun toh sab theek ho jayega.",
    "My roommate has been saying he wants to end his life and has stopped eating or attending class. Please check on him.",
    "I am having severe anxiety attacks before exams and cannot sleep for days. I need counselling urgently.",
    "I feel hopeless since failing my backlog exam and I do not see a reason to continue.",
    "~Mere dost ne khud ko nuksaan pahunchaya hai, please counsellor ko bhejiye."],
  sens="WELFARE")
S("Student Welfare", "Medical Emergency", "Medical Emergency", "Health Centre & Student Welfare", [
    "My roommate collapsed in room {room} and is unconscious, we need an ambulance immediately.",
    "A student met with an accident near the main gate and is bleeding, please send help.",
    "I have severe chest pain and am alone in the hostel, I need medical help urgently.",
    "~Hostel mein ek student ko bahut tez bukhar aur seizure aaya hai, turant doctor bhejiye.",
    "Food poisoning in {block}, around ten students are vomiting and need a hospital.",
    "I was bitten by a dog near the library and the wound is bleeding badly.",
    "A student fainted in the classroom and is not responding. Please send the ambulance.",
    "~Mere dost ka bike accident ho gaya hai gate 2 ke paas, bahut chot lagi hai."],
  sens="MEDICAL")

# ---- Feedback (non-grievance) ----
S("Feedback & Suggestions", "Positive Feedback", "Positive Feedback", "Feedback Registry", [
    "Thank you to the hostel staff for fixing my room issue so quickly in {block}.",
    "The new UMS interface is very easy to use. Great work by the IT team.",
    "The faculty of {course} explains concepts very clearly. Thank you.",
    "The examination cell resolved my marks issue within two days. Really appreciate it.",
    "~Mess ka khana is hafte bahut accha tha, thank you.",
    "The library staff were very helpful during exam week.",
    "The Wi-Fi in {block} has improved a lot recently. Thanks to the IT team.",
    "~SDMA team ne {event} bahut achhe se organise kiya, thank you."])
S("Feedback & Suggestions", "Suggestion", "General Suggestion", "Feedback Registry", [
    "Please install more water coolers near {block}.",
    "It would be helpful to have a mobile app for tracking RMS status.",
    "I suggest adding more seating in the library during exams.",
    "~Exam ke time bus ki sankhya badhai jaye.",
    "Please extend the canteen timings till midnight during exams.",
    "A single page showing all my pending requests would make RMS much easier to use.",
    "~Campus mein aur dustbins lagwaiye {block} ke paas.",
    "It would be nice to get an SMS when my RMS request is answered."])

# ----------------------------------------------------------------------------
# 2. HARMLESS "TRIGGER WORD" RECORDS (contain risky words but are routine)
#    (template, target subcategory, trigger keyword)
# ----------------------------------------------------------------------------
HARMLESS = [
    ("This exam schedule is killing me, please give a gap between {course} and {course2} papers.", "Exam Schedule Concern", "killing"),
    ("The back to back exams are killing us. Please reschedule the {course} exam.", "Exam Schedule Concern", "killing"),
    ("Fees of Rs {amount} are killing my family's budget. Can I pay in instalments?", "Fee Concession Request", "killing"),
    ("I am dying to know my {course} result, it has not been declared yet.", "Result Not Declared", "dying"),
    ("The mess food is so bad that it is depressing. Please improve the quality in {block}.", "Mess Food Quality", "depressing"),
    ("I was admitted to the hospital last week with dengue, please update my attendance for {course}.", "Attendance Shortage Condonation", "hospital"),
    ("I had a minor accident on my bike last week and could not attend classes. Please consider my attendance for {course}.", "Attendance Shortage Condonation", "accident"),
    ("My attendance below 75 percent is a threat to my exam eligibility. Please guide me on condonation for {course}.", "Attendance Shortage Condonation", "threat"),
    ("The Wi-Fi in {block} is so slow I feel like giving up on my assignment submissions. Please fix it.", "Wi-Fi Not Working", "giving up"),
    ("The Wi-Fi issue in {block} is a nightmare, I want to die of boredom waiting for pages to load.", "Wi-Fi Not Working", "die"),
    ("Please share the format of the medical certificate needed to apply for medical leave for {course}.", "Attendance Shortage Condonation", "medical"),
    ("Our club is organising an anti-ragging awareness drive during {event}. How do we register?", "Event Registration Query", "ragging"),
    ("I want to attend the harassment awareness workshop at {event}. When is the next session?", "Event Registration Query", "harassment"),
    ("The lift in {block} almost caused an accident as the door kept closing suddenly. Please repair it.", "Room Maintenance", "accident"),
    ("I am happy to say there is no ragging in {block}, but the Wi-Fi has been down for two days.", "Wi-Fi Not Working", "ragging"),
    ("~Exam schedule ne jaan nikaal di hai, {course} aur {course2} ke beech gap chahiye.", "Exam Schedule Concern", "jaan nikaal"),
    ("There is no harassment in our section, I only want to report that the {course} attendance is wrong.", "Attendance Not Updated", "harassment"),
]

# ----------------------------------------------------------------------------
# 3. SMALL LISTS USED TO FILL SLOTS
# ----------------------------------------------------------------------------
COURSES = ["CSE310", "MTH174", "PHY110", "ECE211", "CSE326", "INT217", "PEL121", "CHE110", "CSE408", "MEC215"]
SECTIONS = ["K23AB", "K23CD", "K23EF", "K23GH", "K24AB", "K24CD", "K24EF", "K24GH", "K22AB", "K22CD", "K25AB", "K25CD"]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
BLOCKS = ["BH-1", "BH-2", "BH-3", "BH-4", "BH-5", "BH-6", "GH-1", "GH-2", "GH-3"]
EVENTS = ["TechFest 2026", "Cultural Night 2026", "Hackathon Spark 2026", "Sports Meet 2026",
          "Fresher's Welcome 2026", "Innovation Expo 2026", "Dance Fiesta 2026"]
AMOUNTS = [8500, 12000, 18500, 25000, 32000, 45000, 60000, 75500]
INCOMPLETE = ["pls help", "not working", "urgent please check", "issue not solved yet", "sir please look into my matter",
              "help", "my problem is still pending", "check once", "please resolve", "kuch kaam nahi kar raha",
              "jaldi dekhiye", "ok", "same issue again", "problem hai", "need help asap", "i have a complaint",
              "please do something", "not received", "still not done", "mera kaam nahi hua"]
PREFIX_EN = ["", "", "", "Respected Sir/Madam, ", "Hello, ", "Sir, ", "Good morning, "]
SUFFIX_EN = ["", "", " Please help.", " Kindly resolve this soon.", " Thank you.", " Kindly look into it.", " Please do the needful."]
SUFFIX_HI = ["", "", " please dekhiye.", " jaldi karo.", " thank you."]
URGENT_EN = [" My exam is tomorrow.", " The last date is {date}.", " The exam starts in two days and I need this urgently."]
URGENT_HI = [" Kal exam hai, jaldi kijiye.", " Last date {date} hai."]
URGENT_ELIGIBLE = {"Attendance Shortage Condonation", "Admit Card Not Generated", "Fee Payment Not Reflected",
                   "Fee Concession Request", "Re-evaluation Request", "Result Not Declared", "Exam Schedule Concern",
                   "Fee Receipt Request"}
ABBR = {r"\bplease\b": "pls", r"\bbecause\b": "bcoz", r"\btomorrow\b": "tmrw", r"\burgently\b": "urgntly"}

ROUTINE_SUBS = [k for k, v in SUBS.items() if v["master"] not in ("Student Welfare", "Feedback & Suggestions")]
WELFARE_SUBS = [k for k, v in SUBS.items() if v["master"] == "Student Welfare"]
FEEDBACK_SUBS = [k for k, v in SUBS.items() if v["master"] == "Feedback & Suggestions"]


def fmt_date(d):
    return d.strftime("%d %b").lstrip("0")


def fresh_slots(fixed=None):
    c1, c2 = rng.sample(COURSES, 2)
    s = dict(course=c1, course2=c2, section=rng.choice(SECTIONS), day=rng.choice(DAYS),
             date=fmt_date(datetime(2026, 10, 25) + timedelta(days=rng.randint(0, 25))),
             paydate=fmt_date(datetime(2026, 9, 5) + timedelta(days=rng.randint(0, 45))),
             amount=rng.choice(AMOUNTS), amount2=rng.choice([20, 40, 60, 100, 250, 500]),
             block=rng.choice(BLOCKS), event=rng.choice(EVENTS))
    if fixed:
        s.update(fixed)
    s["room"] = f"{s['block']}-{rng.randint(101, 520)}"
    return s


def render(template, slots):
    return template.lstrip("~").format(**slots)


def add_noise(text):
    """Make the text look like real student typing. Returns (text, changed_flag)."""
    orig = text
    if rng.random() < 0.10:
        text = text.lower()
    if rng.random() < 0.10:
        text = text.rstrip(".")
    if rng.random() < 0.12:
        words = text.split()
        for _ in range(rng.randint(1, 2)):
            i = rng.randrange(len(words))
            w = words[i]
            if len(w) > 4 and w.isalpha():
                j = rng.randrange(1, len(w) - 2)
                words[i] = w[:j] + w[j + 1] + w[j] + w[j + 2:]
        text = " ".join(words)
    if rng.random() < 0.08:
        for pat, rep in ABBR.items():
            text = re.sub(pat, rep, text, flags=re.I)
    return text, text != orig


def wrap(text, hinglish, urgent=False, slots=None):
    """Add polite prefix/suffix and optional urgency sentence."""
    if urgent:
        text += rng.choice(URGENT_HI if hinglish else URGENT_EN).format(**(slots or {"date": "30 Oct"}))
    if hinglish:
        return text + rng.choice(SUFFIX_HI)
    return rng.choice(PREFIX_EN) + text + rng.choice(SUFFIX_EN)


def priority_of(message_type, sensitive, urgent):
    if sensitive:
        return "P1"
    if urgent:
        return "P2"
    if message_type in ("Enquiry", "Feedback", "Positive Feedback"):
        return "P4"
    return "P3"


def pick_message_type():
    return rng.choices(["Grievance", "Assistance", "Enquiry", "Feedback"], [60, 20, 15, 5])[0]


def pick_selected(sub_name, p_correct=0.55):
    """What the student chose in the dropdowns. ~45% wrong, matching the problem statement."""
    t = SUBS[sub_name]
    if rng.random() < p_correct:
        return t["master"], t["category"], t["sub"], 1
    r = rng.random()
    if r < 0.50:
        same = [SUBS[k] for k in ROUTINE_SUBS if SUBS[k]["master"] == t["master"] and k != sub_name]
        if same:
            o = rng.choice(same)
            return o["master"], o["category"], o["sub"], 0
    if r < 0.85:
        o = SUBS[rng.choice([k for k in ROUTINE_SUBS if k != sub_name])]
        return o["master"], o["category"], o["sub"], 0
    return "Others", "Others", "Others", 0


def pick_selected_for_sensitive(sub_name):
    t = SUBS[sub_name]
    r = rng.random()
    if r < 0.25:
        return t["master"], t["category"], t["sub"], 1
    if r < 0.85:
        o = SUBS[rng.choice(ROUTINE_SUBS)]
        return o["master"], o["category"], o["sub"], 0
    return "Others", "Others", "Others", 0


def contact():
    return None if rng.random() < 0.06 else rng.choice("6789") + "".join(rng.choice("0123456789") for _ in range(9))


# ----------------------------------------------------------------------------
# 4. RECORD BUILDER
# ----------------------------------------------------------------------------
records = []
seen = set()


def build(sub_name, record_type, tmpl_idx=None, fixed=None, cluster_id="NONE", force_unique=True,
          message_type=None, trigger=None, template_override=None, template_label=None):
    t = SUBS[sub_name]
    sens = t["sens"] != "NONE"
    for _ in range(40):
        idx = tmpl_idx if tmpl_idx is not None else rng.randrange(8)
        tmpl = template_override or t["templates"][idx]
        slots = fresh_slots(fixed)
        hinglish = tmpl.startswith("~")
        urgent = (sub_name in URGENT_ELIGIBLE and not sens and record_type in ("valid", "edge_harmless_trigger")
                  and rng.random() < 0.2)
        body = wrap(render(tmpl, slots), hinglish, urgent, slots)
        body, noisy = add_noise(body)
        if not force_unique or body not in seen:
            seen.add(body)
            break
    else:
        return None
    mt = message_type or (rng.choices(["Grievance", "Assistance", "Enquiry", "Feedback"], [50, 20, 15, 15])[0]
                          if sens else ("Positive Feedback" if t["category"] == "Positive Feedback"
                                        else ("Feedback" if t["category"] == "Suggestion" else pick_message_type())))
    sm, sc, ss, correct = pick_selected_for_sensitive(sub_name) if sens else pick_selected(sub_name)
    used = lambda k: ("{" + k + "}") in tmpl
    rec = dict(
        message_type=mt, selected_master=sm, selected_category=sc, selected_subcategory=ss,
        selected_is_correct=correct,
        true_master=t["master"], true_category=t["category"], true_subcategory=t["sub"],
        secondary_subcategory="", description=body, language="hinglish" if hinglish else "english",
        section=slots["section"], hostel_block=slots["block"],
        course_code=slots["course"] if used("course") else "",
        event_name=slots["event"] if used("event") else "",
        contact_no=contact(), record_type=record_type,
        sensitive_label=int(sens), sensitivity_type=t["sens"], trigger_keyword=trigger or "",
        urgent_deadline=int(urgent), priority_label=priority_of(mt, sens, urgent),
        expected_route=t["route"], needs_human_review=int(sens),
        cluster_id=cluster_id, cluster_position=0, hard_negative_of="",
        template_id=template_label or f"{t['code']}-v{idx}",
        has_noise=int(noisy), variant_heldout=int((idx % 4) == 3) if template_override is None else 0,
        created_at=None, expected_action="",
    )
    return rec


# --- 4a. normal / valid records -------------------------------------------------
for name in ROUTINE_SUBS:
    for _ in range(62):
        r = build(name, "valid")
        if r:
            records.append(r)

# --- 4b. sensitive records ------------------------------------------------------
for name in WELFARE_SUBS:
    for _ in range(42):
        r = build(name, "sensitive")
        if r:
            r["needs_human_review"] = 1
            records.append(r)

# --- 4c. feedback ---------------------------------------------------------------
for name in FEEDBACK_SUBS:
    for _ in range(40):
        r = build(name, "valid")
        if r:
            r["expected_route"] = "Feedback Registry"
            records.append(r)

# --- 4d. harmless trigger-word records (must NOT be escalated) --------------------
for i, (tmpl, target, kw) in enumerate(HARMLESS):
    for _ in range(5):
        r = build(target, "edge_harmless_trigger", template_override=tmpl, trigger=kw,
                  template_label=f"HARMLESS-{i:02d}")
        if r:
            r["variant_heldout"] = int(i % 3 == 2)  # one third held out for test
            records.append(r)

# --- 4e. incomplete records ------------------------------------------------------
for _ in range(130):
    text = rng.choice(INCOMPLETE) + rng.choice(["", " sir", " please", " pls", " urgent", " asap", " ??", " again", " plz check"])
    if rng.random() < 0.3:
        text = text.capitalize()
    if text in seen:
        continue
    seen.add(text)
    sub = rng.choice(ROUTINE_SUBS)
    sm, sc, ss, _c = pick_selected(sub, p_correct=0.5)
    mt = pick_message_type()
    records.append(dict(
        message_type=mt, selected_master=sm, selected_category=sc, selected_subcategory=ss, selected_is_correct=0,
        true_master="UNCLEAR", true_category="UNCLEAR", true_subcategory="UNCLEAR", secondary_subcategory="",
        description=text, language="hinglish" if re.search(r"kuch|jaldi|mera|hai", text) else "english",
        section=rng.choice(SECTIONS), hostel_block=rng.choice(BLOCKS), course_code="", event_name="",
        contact_no=contact(), record_type="incomplete", sensitive_label=0, sensitivity_type="NONE",
        trigger_keyword="", urgent_deadline=0, priority_label="P3", expected_route="Manual Triage",
        needs_human_review=1, cluster_id="NONE", cluster_position=0, hard_negative_of="",
        template_id="INCOMPLETE", has_noise=0, variant_heldout=int(rng.random() < 0.2),
        created_at=None, expected_action="REQUEST_MORE_INFO"))

# --- 4f. multi-issue (two problems in one message) -------------------------------
# routine + routine: label = first issue, secondary = second
for _ in range(40):
    a, b = rng.sample(ROUTINE_SUBS, 2)
    ra = build(a, "multi_issue", force_unique=False)
    rb = build(b, "multi_issue", force_unique=False)
    if ra and rb:
        ra["description"] = ra["description"].rstrip() + " Also, " + rb["description"][0].lower() + rb["description"][1:]
        ra["secondary_subcategory"] = rb["true_subcategory"]
        ra["needs_human_review"] = 1
        ra["template_id"] = ra["template_id"] + "+" + rb["template_id"]
        ra["variant_heldout"] = max(ra["variant_heldout"], rb["variant_heldout"])
        seen.add(ra["description"])
        records.append(ra)
# routine + sensitive: the sensitive part must win
for _ in range(35):
    a = rng.choice(ROUTINE_SUBS)
    b = rng.choice(WELFARE_SUBS)
    ra = build(a, "multi_issue_sensitive", force_unique=False)
    rb = build(b, "multi_issue_sensitive", force_unique=False)
    if ra and rb:
        ra["description"] = ra["description"].rstrip() + " Also, " + rb["description"][0].lower() + rb["description"][1:]
        ra["secondary_subcategory"] = ra["true_subcategory"]
        for k in ("true_master", "true_category", "true_subcategory", "sensitivity_type", "expected_route"):
            ra[k] = rb[k]
        ra["sensitive_label"] = 1
        ra["priority_label"] = "P1"
        ra["needs_human_review"] = 1
        ra["urgent_deadline"] = 0
        ra["template_id"] = ra["template_id"] + "+" + rb["template_id"]
        ra["variant_heldout"] = max(ra["variant_heldout"], rb["variant_heldout"])
        seen.add(ra["description"])
        records.append(ra)

# ----------------------------------------------------------------------------
# 5. INCIDENT CLUSTERS ("50 students, one problem")
# ----------------------------------------------------------------------------
CLUSTERS = [
    dict(id="C01", sub="Section Timetable Not Updated", key=("section", "K23AB"), n=30, test=False,
         title="Timetable not updated for section K23AB",
         reply="The timetable for section K23AB will be uploaded on UMS by {d}. Please follow faculty announcements until then."),
    dict(id="C02", sub="Section Timetable Not Updated", key=("section", "K23CD"), n=22, test=False,
         title="Timetable not updated for section K23CD",
         reply="The timetable for section K23CD is being finalised and will be available on UMS by {d}."),
    dict(id="C03", sub="Section Timetable Not Updated", key=("section", "K24EF"), n=18, test=True,
         title="Timetable not updated for section K24EF",
         reply="The timetable for section K24EF will be uploaded on UMS by {d}."),
    dict(id="C04", sub="Event DL Not Updated", key=("event", "TechFest 2026"), n=35, test=False,
         title="Duty leave not updated for TechFest 2026",
         reply="DL for TechFest 2026 will be updated in UMS by {d} for all registered participants and volunteers."),
    dict(id="C05", sub="Event DL Not Updated", key=("event", "Cultural Night 2026"), n=25, test=False,
         title="Duty leave not updated for Cultural Night 2026",
         reply="DL for Cultural Night 2026 has been forwarded to Academic Operations and will reflect by {d}."),
    dict(id="C06", sub="Event DL Not Updated", key=("event", "Hackathon Spark 2026"), n=20, test=True,
         title="Duty leave not updated for Hackathon Spark 2026",
         reply="DL for Hackathon Spark 2026 will be updated by {d}."),
    dict(id="C07", sub="Result Not Declared", key=("course", "CSE310"), n=28, test=False,
         title="Result of CSE310 not declared",
         reply="The CSE310 result is under moderation and will be declared by {d}."),
    dict(id="C08", sub="Wi-Fi Not Working", key=("block", "BH-3"), n=30, test=False,
         title="Wi-Fi down in hostel block BH-3",
         reply="The Wi-Fi outage in BH-3 has been escalated to the network team. Services will be restored by {d}."),
    dict(id="C09", sub="Online Class Link Issue", key=("course", "MTH174"), n=20, test=False,
         title="Online class link not working for MTH174",
         reply="The MTH174 class link has been reported to the faculty. A new link will be shared by {d}."),
    dict(id="C10", sub="Fee Payment Not Reflected", key=("paydate", "20 Oct"), n=25, test=False,
         title="Fee payments made on 20 Oct not reflected (gateway failure)",
         reply="Payments made on 20 Oct failed to sync due to a gateway issue. They will be reconciled by {d}; no re-payment is needed."),
]
KEY_NEEDS_IN_TEXT = {"event", "course", "paydate"}   # cluster text must mention these
incidents = []
cluster_rows = []
for c in CLUSTERS:
    slot_name, slot_val = c["key"]
    t = SUBS[c["sub"]]
    allowed = [i for i, tm in enumerate(t["templates"])
               if slot_name not in KEY_NEEDS_IN_TEXT or ("{" + slot_name + "}") in tm]
    if not c["test"]:
        allowed = [i for i in allowed if i % 4 != 3] or allowed   # keep held-out wordings out of train clusters
    start = datetime(2026, 9, 10) + timedelta(days=rng.randint(0, 35), hours=rng.randint(8, 17))
    rows = []
    for _ in range(c["n"]):
        r = build(c["sub"], "cluster", tmpl_idx=rng.choice(allowed), fixed={slot_name: slot_val},
                  cluster_id=c["id"], force_unique=False, message_type="Grievance" if rng.random() < 0.8 else "Assistance")
        if slot_name == "section":
            r["section"] = slot_val
        if slot_name == "block":
            r["hostel_block"] = slot_val
        r["created_at"] = start + timedelta(minutes=sorted([0] + [rng.uniform(5, 3 * 24 * 60) for _ in range(c["n"] - 1)])[len(rows)])
        r["variant_heldout"] = 0
        r["_is_test_cluster"] = c["test"]
        rows.append(r)
    rows.sort(key=lambda x: x["created_at"])
    for pos, r in enumerate(rows, 1):
        r["cluster_position"] = pos
        r["expected_action"] = "MANUAL_FIRST_RESPONSE" if pos <= 2 else "AUTO_REPLY_KNOWN_ISSUE"
    cluster_rows += rows
    exp = start + timedelta(days=rng.randint(3, 7))
    incidents.append(dict(
        incident_id=f"INC-{c['id'][1:]}", cluster_id=c["id"], title=c["title"], category=t["category"],
        subcategory=t["sub"], match_key_type=slot_name, match_key_value=slot_val,
        reply_template=c["reply"].format(d=fmt_date(exp)), expected_resolution_date=exp.date().isoformat(),
        created_from_request_position=2, linked_request_count=c["n"],
        status="resolved" if start < datetime(2026, 10, 5) else "open",
        created_at=(rows[1]["created_at"]).strftime("%Y-%m-%d %H:%M:%S")))
    # hard negatives: same subcategory, DIFFERENT key value -> must NOT get this incident's reply
    if not c["test"]:
        pool = {"section": SECTIONS, "event": EVENTS, "course": COURSES, "block": BLOCKS,
                "paydate": ["12 Sep", "28 Sep", "4 Oct", "9 Oct"]}[slot_name]
        for _ in range(5):
            other = rng.choice([v for v in pool if v != slot_val])
            r = build(c["sub"], "hard_negative", tmpl_idx=rng.choice(allowed), fixed={slot_name: other},
                      force_unique=True)
            if r:
                if slot_name == "section":
                    r["section"] = other
                if slot_name == "block":
                    r["hostel_block"] = other
                r["hard_negative_of"] = c["id"]
                r["expected_action"] = "ROUTE_NORMAL"
                records.append(r)
records += cluster_rows

# ----------------------------------------------------------------------------
# 6. FINISH: timestamps, ids, actions, split
# ----------------------------------------------------------------------------
base = datetime(2026, 8, 25)
for r in records:
    if r["created_at"] is None:
        r["created_at"] = base + timedelta(minutes=rng.randint(0, 56 * 24 * 60))
    if not r["expected_action"]:
        if r["sensitive_label"]:
            r["expected_action"] = "ESCALATE_SENSITIVE"
        elif r["record_type"] == "valid" and r["true_master"] == "Feedback & Suggestions":
            r["expected_action"] = "LOG_FEEDBACK"
        else:
            r["expected_action"] = "ROUTE_NORMAL"
    if r["sensitive_label"]:
        r["expected_action"] = "ESCALATE_SENSITIVE"

rng.shuffle(records)
records.sort(key=lambda r: r["created_at"])
ids = rng.sample(range(10000, 99999), len(records))
for i, r in enumerate(records):
    r["request_id"] = f"RMS-{i + 1:05d}"
    r["student_ref"] = f"STU{ids[i]}"
    r["created_at"] = r["created_at"].strftime("%Y-%m-%d %H:%M:%S")

df = pd.DataFrame(records)


def assign_split(row):
    if row.get("_is_test_cluster") is True:
        return "test"
    if row["variant_heldout"] == 1:
        return "test"
    return "val" if rng.random() < 0.12 else "train"


df["split"] = df.apply(assign_split, axis=1)
df = df.drop(columns=["_is_test_cluster"], errors="ignore")
cols = ["request_id", "student_ref", "created_at", "message_type",
        "selected_master", "selected_category", "selected_subcategory", "selected_is_correct",
        "description", "language", "contact_no", "section", "hostel_block", "course_code", "event_name",
        "true_master", "true_category", "true_subcategory", "secondary_subcategory",
        "record_type", "sensitive_label", "sensitivity_type", "trigger_keyword",
        "urgent_deadline", "priority_label", "expected_route", "needs_human_review", "expected_action",
        "cluster_id", "cluster_position", "hard_negative_of", "template_id", "variant_heldout", "has_noise", "split"]
df = df[cols]

# ----------------------------------------------------------------------------
# 7. WRITE FILES
# ----------------------------------------------------------------------------
for d in ("config", "data/synthetic", "data/processed", "data/test_set"):
    (ROOT / d).mkdir(parents=True, exist_ok=True)

df.to_csv(ROOT / "data/synthetic/grievances_full.csv", index=False, encoding="utf-8")
df[df.split == "train"].to_csv(ROOT / "data/processed/train.csv", index=False, encoding="utf-8")
df[df.split == "val"].to_csv(ROOT / "data/processed/val.csv", index=False, encoding="utf-8")
df[df.split == "test"].to_csv(ROOT / "data/test_set/test.csv", index=False, encoding="utf-8")
pd.DataFrame(incidents).to_csv(ROOT / "data/synthetic/incidents.csv", index=False, encoding="utf-8")

tree, routes = {}, {}
for v in SUBS.values():
    tree.setdefault(v["master"], {}).setdefault(v["category"], []).append(v["sub"])
    routes[v["sub"]] = v["route"]
(ROOT / "config/category_tree.json").write_text(
    json.dumps({"_note": "PLACEHOLDER tree. Replace with the real RMS dropdown values.", "tree": tree},
               indent=2, ensure_ascii=False), encoding="utf-8")
(ROOT / "config/routing_table.yaml").write_text(
    yaml.safe_dump({"default": "General Grievance Queue", "unclear": "Manual Triage", "routes": routes},
                   sort_keys=False, allow_unicode=True), encoding="utf-8")

print(f"Total records: {len(df)}")
print(df.split.value_counts().to_string())
print("\nRecord types:\n", df.record_type.value_counts().to_string())
print("\nMaster categories:\n", df.true_master.value_counts().to_string())
print(f"\nSelected category wrong: {1 - df[df.true_master.ne('UNCLEAR')].selected_is_correct.mean():.0%}")
