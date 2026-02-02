import shopify
import json
import os
from termcolor import colored

def setup_shopify_session():
    print(colored("\n--- Configuración de Shopify ---", "cyan"))
    shop_url = input("Ingresa la URL de tu tienda (ej: mi-tienda.myshopify.com): ").strip()
    # Clean url if user pastes protocol
    shop_url = shop_url.replace('https://', '').replace('http://', '').replace('/', '')
    
    access_token = input("Ingresa tu Token de Acceso Admin (shpat_...): ").strip()
    
    if not shop_url or not access_token:
        print(colored("Error: URL y Token son obligatorios.", "red"))
        return None

    try:
        session = shopify.Session(shop_url, '2023-04', access_token)
        shopify.ShopifyResource.activate_session(session)
        shop = shopify.Shop.current()
        print(colored(f"✅ Conectado exitosamente a: {shop.name}", "green"))
        return session
    except Exception as e:
        print(colored(f"❌ Error conectando a Shopify: {e}", "red"))
        return None

def inspect_orders():
    print(colored("\n--- Inspeccionando Pedidos Recientes ---", "cyan"))
    print("Buscando los últimos 5 pedidos para encontrar dónde se guardan los números de AliExpress...")
    
    try:
        orders = shopify.Order.find(limit=5, status='any')
        
        if not orders:
            print(colored("No se encontraron pedidos en la tienda.", "yellow"))
            return

        found_ali_info = False
        
        for order in orders:
            print(colored(f"\n📦 Pedido Shopify: {order.name} (ID: {order.id})", "yellow"))
            print(f"   Created At: {order.created_at}")
            
            # Inspect potential fields
            print(f"   🔹 Note (Notas): {order.note if order.note else 'Vacío'}")
            print(f"   🔹 Tags (Etiquetas): {order.tags if order.tags else 'Vacío'}")
            
            # Note Attributes are key-value pairs
            attributes = getattr(order, 'note_attributes', [])
            attr_str = ", ".join([f"{a.name}: {a.value}" for a in attributes]) if attributes else "Vacío"
            print(f"   🔹 Note Attributes: {attr_str}")
            
            # Look deeply into line items just in case (rare but possible DSers puts it there)
            # for item in order.line_items:
            #    print(f"      - Item: {item.title}")
        
        print(colored("\n--- Pregunta al Usuario ---", "magenta"))
        print("Revisa los datos de arriba de tus pedidos recientes.")
        print("¿Ves el 'Número de Orden de AliExpress' (ej: 8123...) en alguno de esos campos?")
        print("1. En 'Note' (Notas)")
        print("2. En 'Tags' (Etiquetas)")
        print("3. En 'Note Attributes' (Atributos de nota)")
        print("4. No lo veo :(")
        
        answer = input("\nSelecciona una opción (1-4): ")
        
        config = {}
        if answer == '1':
            config['ali_id_location'] = 'note'
        elif answer == '2':
            config['ali_id_location'] = 'tags'
        elif answer == '3':
            config['ali_id_location'] = 'note_attributes'
            key_name = input("¿Cuál es el nombre exacto del atributo? (ej: 'AliExpress Order ID'): ")
            config['ali_id_attribute_name'] = key_name
        else:
            print(colored("\n⚠️  Si no ves el número de AliExpress, NO PODEMOS automatizar esto solo con Shopify.", "red"))
            print("Necesitaremos acceso a la API de DSers o exportar CSVs.")
            config['ali_id_location'] = 'unknown'

        # Save partial config
        with open('../config/user_config.json', 'w') as f:
            json.dump(config, f, indent=4)
            print(colored("\n✅ Configuración guardada en config/user_config.json", "green"))
            
    except Exception as e:
        print(colored(f"Error recuperando pedidos: {e}", "red"))

if __name__ == "__main__":
    print(colored("=== Diagnóstico de Integración Shopify ===", "blue"))
    if setup_shopify_session():
        inspect_orders()
