#!/usr/bin/env python3
"""
Populate the database with realistic phylogenetic tree examples.
These are simplified but scientifically accurate representations of real evolutionary relationships.
"""
import requests
import json

API_BASE = "http://127.0.0.1:8000"

# Collection of realistic phylogenetic trees
# Note: Using simple metadata to avoid LanceDB schema evolution issues
TREES = [
    # === PRIMATES & HOMINIDS ===
    {
        "name": "Great Apes Evolution",
        "newick": "((((Homo_sapiens:6.4,Pan_troglodytes:6.4):1.0,Pan_paniscus:7.4):2.0,Gorilla_gorilla:9.4):5.0,(Pongo_pygmaeus:12.4,Pongo_abelii:12.4):2.0);"
    },
    {
        "name": "Old World Monkeys",
        "newick": "(((Macaca_mulatta:8.0,Macaca_fascicularis:8.0):4.0,(Papio_anubis:10.0,Theropithecus:10.0):2.0):6.0,((Colobus:12.0,Piliocolobus:12.0):3.0,Nasalis:15.0):3.0);"
    },
    {
        "name": "Hominin Evolution",
        "newick": "((((Homo_sapiens:0.2,Homo_neanderthalensis:0.2):0.3,Homo_heidelbergensis:0.5):0.5,Homo_erectus:1.0):1.0,(Australopithecus_afarensis:1.5,Australopithecus_africanus:1.5):0.5);"
    },
    
    # === VIRUSES ===
    {
        "name": "SARS-CoV-2 Variants",
        "newick": "((((B.1.1.7_Alpha:0.015,B.1.351_Beta:0.018):0.005,P.1_Gamma:0.020):0.008,((B.1.617.2_Delta:0.025,AY.4.2_Delta_Plus:0.028):0.003,B.1.1.529_Omicron:0.045):0.010):0.002,Original_Wuhan:0.001);"
    },
    {
        "name": "Influenza A Subtypes",
        "newick": "(((H1N1_1918:0.30,H1N1_2009:0.35):0.10,H2N2:0.40):0.15,((H3N2:0.45,H3N8:0.45):0.05,(H5N1:0.40,H7N9:0.42):0.08):0.10);"
    },
    {
        "name": "HIV-1 Subtypes",
        "newick": "((((Subtype_A1:0.08,Subtype_A2:0.08):0.02,Subtype_C:0.10):0.03,((Subtype_B:0.09,Subtype_D:0.09):0.02,Subtype_F1:0.11):0.02):0.05,(Subtype_G:0.14,CRF02_AG:0.14):0.04);"
    },
    {
        "name": "Hepatitis C Genotypes",
        "newick": "(((Genotype_1a:0.12,Genotype_1b:0.12):0.05,Genotype_4:0.17):0.08,((Genotype_2:0.18,Genotype_3:0.18):0.04,(Genotype_5:0.19,Genotype_6:0.19):0.03):0.05);"
    },
    
    # === MAMMALS ===
    {
        "name": "Mammalian Orders",
        "newick": "(((((Homo:85,Mus:85):15,Canis:100):10,(Bos:95,Sus:95):15):5,((Loxodonta:90,Trichechus:90):15,Orycteropus:105):5):20,(Ornithorhynchus:110,Tachyglossus:110):20);"
    },
    {
        "name": "Canidae Family (Dogs and Foxes)",
        "newick": "(((Canis_lupus:2.0,Canis_familiaris:2.0):1.5,(Canis_latrans:3.0,Canis_aureus:3.0):0.5):2.0,((Vulpes_vulpes:3.5,Vulpes_zerda:3.5):1.0,Urocyon:4.5):1.0);"
    },
    {
        "name": "Felidae Family (Cats)",
        "newick": "((((Panthera_leo:3.5,Panthera_tigris:3.5):1.0,Panthera_pardus:4.5):2.0,(Acinonyx:5.5,Puma:5.5):1.0):3.0,((Felis_catus:6.0,Felis_silvestris:6.0):1.5,Lynx:7.5):2.0);"
    },
    {
        "name": "Cetaceans (Whales and Dolphins)",
        "newick": "(((Balaenoptera_musculus:12.0,Balaenoptera_physalus:12.0):3.0,Megaptera:15.0):5.0,((Tursiops:14.0,Delphinus:14.0):2.0,(Orcinus:13.0,Globicephala:13.0):3.0):4.0);"
    },
    {
        "name": "Bears (Ursidae)",
        "newick": "(((Ursus_arctos:2.5,Ursus_maritimus:2.5):1.5,Ursus_americanus:4.0):3.0,((Ailuropoda:5.0,Tremarctos:5.0):1.0,(Melursus:4.5,Helarctos:4.5):1.5):1.0);"
    },
    
    # === BIRDS ===
    {
        "name": "Ratites (Flightless Birds)",
        "newick": "(((Struthio_camelus:60.0,Rhea:60.0):15.0,(Dromaius:65.0,Casuarius:65.0):10.0):10.0,((Apteryx:70.0,Tinamus:70.0):8.0,Crypturellus:78.0):7.0);"
    },
    {
        "name": "Corvidae (Crows and Ravens)",
        "newick": "((((Corvus_corax:5.0,Corvus_brachyrhynchos:5.0):2.0,Corvus_corone:7.0):3.0,(Pica_pica:8.0,Cyanopica:8.0):2.0):4.0,((Garrulus:10.0,Perisoreus:10.0):2.0,Nucifraga:12.0):2.0);"
    },
    {
        "name": "Raptors (Birds of Prey)",
        "newick": "(((Aquila_chrysaetos:15.0,Haliaeetus:15.0):5.0,(Buteo:17.0,Accipiter:17.0):3.0):8.0,((Falco_peregrinus:18.0,Falco_rusticolus:18.0):4.0,Caracara:22.0):6.0);"
    },
    
    # === REPTILES ===
    {
        "name": "Crocodilians",
        "newick": "(((Crocodylus_niloticus:35.0,Crocodylus_porosus:35.0):10.0,(Alligator:40.0,Caiman:40.0):5.0):15.0,(Gavialis:55.0,Tomistoma:55.0):5.0);"
    },
    {
        "name": "Pythons and Boas",
        "newick": "((((Python_reticulatus:20.0,Python_molurus:20.0):5.0,Python_regius:25.0):10.0,(Boa_constrictor:28.0,Epicrates:28.0):7.0):8.0,(Eunectes:38.0,Corallus:38.0):5.0);"
    },
    
    # === FISH ===
    {
        "name": "Salmonids (Salmon Family)",
        "newick": "(((Salmo_salar:15.0,Salmo_trutta:15.0):5.0,(Oncorhynchus_mykiss:17.0,Oncorhynchus_tshawytscha:17.0):3.0):8.0,((Salvelinus:22.0,Hucho:22.0):3.0,Thymallus:25.0):3.0);"
    },
    {
        "name": "Cichlids (African Great Lakes)",
        "newick": "((((Oreochromis:2.0,Sarotherodon:2.0):1.0,Tilapia:3.0):2.0,(Haplochromis:4.0,Astatotilapia:4.0):1.0):3.0,((Tropheus:5.0,Petrochromis:5.0):1.5,Cyphotilapia:6.5):1.5);"
    },
    {
        "name": "Sharks",
        "newick": "(((Carcharodon:45.0,Isurus:45.0):10.0,(Prionace:50.0,Galeocerdo:50.0):5.0):15.0,((Sphyrna:55.0,Eusphyra:55.0):8.0,(Rhincodon:58.0,Cetorhinus:58.0):5.0):7.0);"
    },
    
    # === BACTERIA ===
    {
        "name": "Bacterial 16S rRNA",
        "newick": "((((E_coli:0.02,Salmonella:0.02):0.03,Pseudomonas:0.05):0.04,((Bacillus:0.04,Staphylococcus:0.04):0.02,Streptococcus:0.06):0.03):0.05,(Mycobacterium:0.10,Corynebacterium:0.10):0.05);"
    },
    {
        "name": "Gut Microbiome Representatives",
        "newick": "((((Bacteroides:0.05,Prevotella:0.05):0.02,Parabacteroides:0.07):0.03,((Faecalibacterium:0.06,Roseburia:0.06):0.02,Eubacterium:0.08):0.02):0.04,(Bifidobacterium:0.10,Lactobacillus:0.10):0.04);"
    },
    {
        "name": "Pathogenic Bacteria",
        "newick": "(((Staphylococcus_aureus:0.03,MRSA:0.03):0.02,(Streptococcus_pneumoniae:0.04,Streptococcus_pyogenes:0.04):0.01):0.04,((Pseudomonas_aeruginosa:0.05,Klebsiella:0.05):0.02,(Clostridium_difficile:0.06,Clostridioides:0.06):0.01):0.03);"
    },
    
    # === PLANTS ===
    {
        "name": "Flowering Plants (Angiosperms)",
        "newick": "((((Rosa:50,Malus:50):10,Prunus:60):15,(Glycine:65,Phaseolus:65):10):20,((Solanum:70,Nicotiana:70):15,(Arabidopsis:75,Brassica:75):10):10);"
    },
    {
        "name": "Grasses (Poaceae)",
        "newick": "((((Triticum:12.0,Hordeum:12.0):3.0,Avena:15.0):5.0,((Oryza:16.0,Zea:16.0):2.0,Sorghum:18.0):2.0):8.0,((Bambusa:20.0,Phyllostachys:20.0):3.0,Saccharum:23.0):5.0);"
    },
    {
        "name": "Conifers",
        "newick": "(((Pinus_sylvestris:80.0,Pinus_strobus:80.0):15.0,(Picea:88.0,Abies:88.0):7.0):20.0,((Sequoia:95.0,Sequoiadendron:95.0):10.0,(Taxodium:100.0,Metasequoia:100.0):5.0):15.0);"
    },
    {
        "name": "Citrus Species",
        "newick": "(((Citrus_sinensis:4.0,Citrus_reticulata:4.0):1.5,(Citrus_limon:5.0,Citrus_aurantifolia:5.0):0.5):2.0,((Citrus_maxima:5.5,Citrus_medica:5.5):1.0,Citrus_paradisi:6.5):1.0);"
    },
    
    # === FUNGI ===
    {
        "name": "Edible Mushrooms",
        "newick": "((((Agaricus_bisporus:25.0,Agaricus_campestris:25.0):5.0,Pleurotus:30.0):10.0,(Lentinula:35.0,Flammulina:35.0):5.0):15.0,((Boletus:40.0,Suillus:40.0):8.0,(Cantharellus:42.0,Craterellus:42.0):6.0):7.0);"
    },
    {
        "name": "Yeast Species",
        "newick": "(((Saccharomyces_cerevisiae:20.0,Saccharomyces_bayanus:20.0):5.0,(Candida_albicans:22.0,Candida_glabrata:22.0):3.0):10.0,((Pichia:28.0,Kluyveromyces:28.0):4.0,Schizosaccharomyces:32.0):3.0);"
    },
    
    # === HUMAN GENETICS ===
    {
        "name": "Human Mitochondrial Haplogroups",
        "newick": "((((H:0.01,V:0.01):0.005,J:0.015):0.01,((T:0.02,U:0.02):0.005,K:0.025):0.005):0.02,(((L0:0.05,L1:0.05):0.02,L2:0.07):0.01,L3:0.08):0.01);"
    },
    {
        "name": "Human Y-Chromosome Haplogroups",
        "newick": "(((R1a:0.015,R1b:0.015):0.005,(I1:0.018,I2:0.018):0.002):0.010,((E1b:0.022,J2:0.022):0.004,((G:0.024,N:0.024):0.002,Q:0.026):0.002):0.006);"
    },
    {
        "name": "HLA Allele Families",
        "newick": "((((HLA_A02:0.01,HLA_A03:0.01):0.005,HLA_A01:0.015):0.008,(HLA_B07:0.018,HLA_B08:0.018):0.005):0.010,((HLA_C04:0.022,HLA_C07:0.022):0.004,HLA_DR15:0.026):0.007);"
    },
    
    # === INSECTS ===
    {
        "name": "Drosophila Species",
        "newick": "((((D_melanogaster:25.0,D_simulans:25.0):5.0,D_sechellia:30.0):10.0,(D_yakuba:35.0,D_erecta:35.0):5.0):15.0,((D_pseudoobscura:42.0,D_persimilis:42.0):5.0,D_willistoni:47.0):3.0);"
    },
    {
        "name": "Mosquito Species",
        "newick": "(((Aedes_aegypti:40.0,Aedes_albopictus:40.0):10.0,(Anopheles_gambiae:45.0,Anopheles_stephensi:45.0):5.0):15.0,((Culex_pipiens:50.0,Culex_quinquefasciatus:50.0):8.0,Culiseta:58.0):7.0);"
    },
    {
        "name": "Honeybees and Relatives",
        "newick": "(((Apis_mellifera:15.0,Apis_cerana:15.0):5.0,(Bombus_terrestris:17.0,Bombus_impatiens:17.0):3.0):8.0,((Megachile:20.0,Osmia:20.0):4.0,Xylocopa:24.0):4.0);"
    },
    
    # === MARINE LIFE ===
    {
        "name": "Sea Turtles",
        "newick": "(((Chelonia_mydas:55.0,Eretmochelys:55.0):10.0,(Caretta:60.0,Lepidochelys:60.0):5.0):15.0,(Dermochelys:75.0,Natator:75.0):5.0);"
    },
    {
        "name": "Cephalopods",
        "newick": "(((Octopus_vulgaris:80.0,Enteroctopus:80.0):15.0,(Sepia:88.0,Sepioteuthis:88.0):7.0):20.0,((Loligo:95.0,Dosidicus:95.0):10.0,Nautilus:105.0):10.0);"
    },
    
    # === MODEL ORGANISMS ===
    {
        "name": "Model Organisms",
        "newick": "(((Homo_sapiens:100.0,Mus_musculus:100.0):50.0,(Danio_rerio:120.0,Xenopus:120.0):30.0):100.0,((Drosophila:180.0,C_elegans:180.0):40.0,(Arabidopsis:200.0,S_cerevisiae:200.0):20.0):30.0);"
    },
    {
        "name": "Laboratory Mouse Strains",
        "newick": "((((C57BL6:0.5,C57BL10:0.5):0.3,BALB_c:0.8):0.4,(129S1:1.0,129X1:1.0):0.2):0.6,((DBA2:1.2,A_J:1.2):0.3,(FVB:1.3,SJL:1.3):0.2):0.3);"
    }
]


def ingest_tree(tree_data):
    """Ingest a single tree into the database."""
    try:
        response = requests.post(
            f"{API_BASE}/trees/ingest",
            json=tree_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Added: {result['name']} ({result['num_leaves']} leaves, {result['num_nodes']} nodes)")
            return result
        else:
            print(f"✗ Failed to add {tree_data['name']}: {response.text}")
            return None
    except Exception as e:
        print(f"✗ Error adding {tree_data['name']}: {e}")
        return None


def main():
    print("=" * 60)
    print("Populating database with phylogenetic trees...")
    print("=" * 60)
    
    # First, check if server is running
    try:
        response = requests.get(f"{API_BASE}/trees")
        existing = response.json()
        print(f"\nCurrently {len(existing)} trees in database.\n")
    except Exception as e:
        print(f"Error: Cannot connect to server at {API_BASE}")
        print("Make sure the server is running with: uvicorn catalog.main:app --reload")
        return
    
    # Ingest all trees
    added = 0
    for tree_data in TREES:
        result = ingest_tree(tree_data)
        if result:
            added += 1
    
    print("\n" + "=" * 60)
    print(f"Done! Added {added}/{len(TREES)} trees to the database.")
    print("=" * 60)
    
    # Show final count
    response = requests.get(f"{API_BASE}/trees")
    total = len(response.json())
    print(f"\nTotal trees in database: {total}")


if __name__ == "__main__":
    main()

