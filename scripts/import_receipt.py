import sqlite3
import re
import os

# --- PASTE YOUR NEW DATA HERE ---
RAW_DATA = """
Items in your order (45)
QuantityWeightTotalAmazon Grocery, Beef Stew Meat, Boneless, USDA Choice, Weight Varies11.27 lb ($8.99/lb)$11.42Weight adjusted from est. 1.10 lb
Amazon Fresh Brand, Atlantic Salmon Skin On Fillet Portions, 12 Oz, Responsibly Sourced (Previously Frozen)1$8.99Smucker's Natural Creamy Peanut Butter, 16 Ounces1$3.29BelGioioso, Fresh Mozzarella, Ball, 8 oz1$3.89Downy Fabric Softener Liquid, April Fresh Scent, 111 fl oz, 150 Loads1$10.97Amazon Grocery, Organic Basil, 0.5 Oz (Previously Fresh Brand, Packaging May Vary)1$1.99Red Raspberries, 6 oz1$2.49Amazon Fresh, Multigrain Sandwich Bread, 24 Oz1$2.59Amazon Brand - Happy Belly Tropical Fruit Mix, 16 oz1$2.39Amazon Brand - Happy Belly Shredded Pizza Blend Four Cheese (mozzarella, smoked provolone, Parmesan and Romano), 8 oz1$1.49Florida's Natural, Orange Juice Some Pulp, 52 Fl Oz1$3.49Red Bell Pepper, 1 Each1$1.29Wonderful Seedless Lemons 1lb Bag, 16 Oz1$2.49siggi's® Icelandic Strained Nonfat Yogurt, Vanilla, 24 oz. - Thick, Protein-Rich Yogurt Snack1$4.99Nature Made Zinc 30 mg, Dietary Supplement for Immune Health and Antioxidant Support, 100 Tablets, 100 Day Supply1$3.39Great Grains Raisins Dates and Pecans Breakfast Cereal, Raisin Cereal with Sweet Dates and Granola Clusters, Non-GMO Project Verified, 16 OZ Box1$4.79Amazon Grocery, Jasmine Long Grain Rice, 2 Lb (Previously Amazon Fresh, Packaging May Vary)1$2.66ARM & HAMMER Plus OxiClean Odor Blasters Fresh Burst, 77 Loads Liquid Laundry Detergent, 100.5 Fl oz1$8.98365 by Whole Foods Market, Mushrooms Mixed Organic, 10 Ounce1$3.99Strawberries, 1 Lb1$2.69Amazon Fresh , Pie Crusts, 15 Oz, 2 Ct (Previously Happy Belly, Packaging May Vary)1$2.49365 by Whole Foods Market, Hass Avocados, 4 Count1$2.99Sunset, Sugar Bombs, Grape Tomatoes On The Vine, 12 oz1$2.89Thomas' 100% Whole Wheat Bagels, 6 Pre-Sliced Bagels with No High Fructose Corn Syrup, 20 Oz1$3.49Just Bare® All Natural Fresh Chicken Thighs | Family Pack | No Antibiotics Ever | Bone-In | 2.25 LB1$5.60bubly Sparkling Water, Strawberry Sunset, Zero Sugar & Zero Calories, Seltzer Water, 12 Fl Oz Cans (Pack of 8)1$4.49365 by Whole Foods Market, Pizza Crust Whole Wheat Thin And Crispy Organic, 10 Ounce1$3.99Amazon Fresh Brand, On The Vine Tomatoes, 24 Oz1$2.19Green Onions (Scallions), One Bunch1$0.99Amazon Grocery, Cage Free Large White Eggs, Grade A, 1 Dozen (Previously Amazon Fresh, Packaging May Vary)1$5.49Amazon Fresh Brand, Whole Baby Bella Mushrooms, 8 Oz1$1.49365 by Whole Foods Market, Organic Light Amber Wildflower Honey, 12 Ounce1$4.99Dulcinea Farm Black Jam Grapes, 1 Lb1$3.99Genova Premium Albacore Tuna in Olive Oil, 5 Ounce Can (Pack of 1), Wild Caught Canned Tuna, Solid White2$4.98Wonderful Halos Mandarins, 3 Pound (Pack of 1)1$3.99Classico Signature Recipes Traditional Tomato Spaghetti and Pizza Sauce (14 oz Jar)1$2.92Banana Bunch (4-5 Count)1$0.99Taylor Farms Classic Garden Salad 12oz1$1.89Amazon Grocery, Yellow Onions, 3 Lb (Previously Fresh Brand, Packaging May Vary)1$1.99Tuttorosso Delicious Crushed Tomatoes with basil Canned Tomatoes, 28oz2$3.78365 by Whole Foods Market, Milk 2% Organic Homogenized, 64 Fl Oz1$2.98365 by Whole Foods Market, Organic Raspberry Fruit Spread, 17 Ounce1$4.49Toblerone Milk Chocolate Bar with Honey and Almond Nougat, 3.52 oz1$2.99
"""

def import_data():
    # 1. Connect to Database
    db_path = "agent_data.db"
    # We don't check for existence because we want to create it if it's missing
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Ensure the table exists
    c.execute('''CREATE TABLE IF NOT EXISTS purchase_history 
                 (item_name TEXT PRIMARY KEY, count INTEGER DEFAULT 1)''')

    # 2. Parse the Text
    # Remove header junk and newlines to make one long string
    clean_text = RAW_DATA.replace("Items in your order", "").replace("QuantityWeightTotal", "").replace("\n", " ")
    
    # Remove promotion text which messes up splitting
    # Example: "$0.40 promotion applied"
    clean_text = re.sub(r'\$\d+\.\d+\s+promotion applied', '', clean_text)

    # Split by the price pattern: Number + $ + Digits + . + Digits
    # This regex handles cases like "1$1.73" or "2$4.98"
    # (\d+\$\d+\.\d+) captures the price block
    tokens = re.split(r'(\d+\$\d+\.\d+)', clean_text)
    
    items_found = []
    
    for token in tokens:
        token = token.strip()
        # Filter out prices ($) and empty strings and header junk
        if not token or "$" in token or "Order #" in token or "Ordered" in token:
            continue
        
        # Clean up the item name
        # The quantity number (e.g. '1' or '2') is usually stuck to the end of the name
        # Example: "Peanut Butter1" -> "Peanut Butter"
        item_name = re.sub(r'\d+$', '', token).strip() 
        
        if len(item_name) > 3: 
            items_found.append(item_name)

    # 3. Insert into DB
    print(f"🔍 Found {len(items_found)} items.")
    count_new = 0
    
    for item in items_found:
        print(f"   -> {item}")
        try:
            # Upsert: Add 1 to count if exists, else insert
            c.execute("""
                INSERT INTO purchase_history (item_name, count) 
                VALUES (?, 1) 
                ON CONFLICT(item_name) DO UPDATE SET count = count + 1
            """, (item,))
            count_new += 1
        except Exception as e:
            print(f"Error saving {item}: {e}")

    conn.commit()
    conn.close()
    print("-" * 30)
    print(f"✅ Successfully trained AI on {count_new} items.")

if __name__ == "__main__":
    import_data()