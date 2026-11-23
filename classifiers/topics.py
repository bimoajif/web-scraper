import re
from collections import defaultdict


TOPIC_KEYWORDS = {

    "Taxation": [
        "pajak", "pph", "ppn", "pbb",
        "pajak daerah", "penerimaan pajak",
        "restitusi", "wajib pajak",
        "tax amnesty", "tarif pajak"
    ],

    "Customs & Excise": [
        "bea cukai", "kepabeanan", "cukai",
        "impor", "ekspor", "barang ilegal",
        "rokok ilegal", "penyelundupan"
    ],

    "Politics": [
        "pemilu", "pilkada", "partai politik",
        "dpr", "dprd", "presiden",
        "gubernur", "bupati", "politik"
    ],

    "Government": [
        "pemerintah", "kementerian",
        "kebijakan pemerintah",
        "pelayanan publik", "anggaran daerah",
        "apbd", "birokrasi"
    ],

    "Economy": [
        "ekonomi", "inflasi", "pertumbuhan ekonomi",
        "perekonomian", "investasi",
        "nilai tukar", "produk domestik bruto"
    ],

    "Market": [
        "harga beras", "harga cabai",
        "harga sembako", "harga pangan",
        "pasar", "perdagangan",
        "stok pangan", "daya beli"
    ],

    "Infrastructure": [
        "jalan", "jembatan", "pembangunan",
        "infrastruktur", "pelabuhan",
        "bandara", "jalan rusak"
    ],

    "Education": [
        "sekolah", "universitas", "pendidikan",
        "guru", "siswa", "mahasiswa",
        "beasiswa"
    ],

    "Health": [
        "rumah sakit", "kesehatan",
        "dokter", "pasien", "puskesmas",
        "penyakit", "stunting"
    ],

    "Law & Crime": [
        "korupsi", "polisi", "kriminal",
        "kejaksaan", "pengadilan",
        "tersangka", "penangkapan"
    ],

    "Environment & Disaster": [
        "banjir", "kebakaran", "longsor",
        "bencana", "lingkungan",
        "cuaca ekstrem", "karhutla"
    ],

    "Agriculture & Fisheries": [
        "pertanian", "perkebunan",
        "petani", "nelayan", "perikanan",
        "sawit", "hasil panen"
    ],

    "Tourism": [
        "pariwisata", "wisata",
        "destinasi wisata", "hotel",
        "wisatawan", "objek wisata"
    ]
}


def classify_topics(title, content=""):

    text = f"{title} {content}".lower()

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)

    scores = defaultdict(int)
    matched_keywords = defaultdict(list)

    for topic, keywords in TOPIC_KEYWORDS.items():

        for keyword in keywords:

            pattern = (
                r"(?<!\w)"
                + re.escape(keyword.lower())
                + r"(?!\w)"
            )

            matches = re.findall(pattern, text)

            if matches:
                scores[topic] += len(matches)
                matched_keywords[topic].append(keyword)

    if not scores:
        return {
            "topic": "Other",
            "topics": ["Other"],
            "keywords": [],
            "confidence": 0.0
        }

    ranked = sorted(
        scores.items(),
        key=lambda x: x[1],
        reverse=True
    )

    primary_topic = ranked[0][0]

    # Include secondary topics with at least
    # 50% of the primary topic's score.
    secondary_topics = [
        topic
        for topic, score in ranked[1:]
        if score >= ranked[0][1] * 0.5
    ]

    all_topics = [
        primary_topic
    ] + secondary_topics

    keywords = []

    for topic in all_topics:
        keywords.extend(matched_keywords[topic])

    total_score = sum(scores.values())

    confidence = (
        ranked[0][1] / total_score
        if total_score
        else 0
    )

    return {
        "topic": primary_topic,
        "topics": all_topics,
        "keywords": list(dict.fromkeys(keywords)),
        "confidence": round(confidence, 2)
    }