import json
import os
import logging
import subprocess
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

class JSONGenerator:
    def __init__(self, base_dir='scraped_data', input_file='renesas_applications.json', output_file='data.json'):
        """Initialize the generator with paths"""
        self.base_dir = Path(base_dir)
        self.input_file = input_file
        self.output_file = output_file
        self.consolidated_data = {}
        
    def find_block_diagrams(self):
        """Find all block_diagram.svg files in the directory structure"""
        found_diagrams = []
        
        try:
            # Walk through all directories
            for root, dirs, files in os.walk(self.base_dir):
                root_path = Path(root)
                
                # Check if both block_diagram.svg and content.json exist
                if 'block_diagram.svg' in files and 'content.json' in files:
                    # Get the relative path components
                    rel_path = root_path.relative_to(self.base_dir)
                    parts = list(rel_path.parts)
                    
                    if len(parts) >= 3:  # We need category/subcategory/application
                        diagram_info = {
                            'category': parts[0],
                            'subcategory': parts[1],
                            'application': parts[2],
                            'diagram_path': root_path / 'block_diagram.svg',
                            'content_path': root_path / 'content.json'
                        }
                        found_diagrams.append(diagram_info)
                        logging.info(f"Found block diagram in {root}")
                    
        except Exception as e:
            logging.error(f"Error scanning directories: {str(e)}")
            
        return found_diagrams

    def read_json_file(self, filepath):
        """Read and parse a JSON file"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error reading JSON file {filepath}: {str(e)}")
            return None

    def get_block_diagram_data(self, svg_path, content_path):
        """Get overview and block diagram data"""
        try:
            # Read content.json
            content_data = self.read_json_file(content_path)
            if not content_data:
                return None
                
            try:
                # Create images directory if doesn't exist 
                images_dir = Path('block_diagrams')
                images_dir.mkdir(exist_ok=True)
                
                # Create subdirectories to match original structure
                rel_path = svg_path.relative_to(self.base_dir)
                category = rel_path.parts[0]
                subcategory = rel_path.parts[1]
                application = rel_path.parts[2]
                
                category_dir = images_dir / category
                subcategory_dir = category_dir / subcategory
                subcategory_dir.mkdir(parents=True, exist_ok=True)
                
                # Generate PNG filename and path
                png_filename = f"{application}.png"
                png_path = subcategory_dir / png_filename
                
                # Convert SVG to PNG using rsvg-convert
                try:
                    subprocess.run([
                        'rsvg-convert',
                        '-w', '1200',  # Width
                        '-h', '900',   # Height
                        '-o', str(png_path),
                        str(svg_path)
                    ], check=True)

                except Exception as e:
                    logging.error(f"Error Subprocess SVG to PNG: {str(e)}")
                    return None
                # Return relative path from block_diagrams directory
                relative_png_path = png_path.relative_to(images_dir)
                
                # Return structured data
                return {
                    "overview": content_data.get('overview', {}),
                    "block_diagram": f"block_diagrams/{str(relative_png_path)}"
                }
                    
            except Exception as e:
                logging.error(f"Error converting SVG to PNG: {str(e)}")
                return None
                
        except Exception as e:
            logging.error(f"Error reading block diagram data: {str(e)}")
            return None
        
    def find_application_link(self, category, subcategory, application_name):
        """Find application link from applications.json"""
        try:
            apps_data = self.read_json_file(self.input_file)
            if not apps_data:
                return None
                
            # Look through applications to find matching one
            if category in apps_data:
                cat_data = apps_data[category]
                if 'subcategories' in cat_data:
                    for subcat_name, subcat_data in cat_data['subcategories'].items():
                        # Check if subcategory names match approximately
                        if self.names_match(subcat_name, subcategory):
                            for app in subcat_data.get('applications', []):
                                if self.names_match(app['title'], application_name):
                                    return app['link']
            return None
            
        except Exception as e:
            logging.error(f"Error finding application link: {str(e)}")
            return None

    def names_match(self, name1, name2):
        """Compare names ignoring special characters and case"""
        def clean_name(name):
            return ''.join(c.lower() for c in name if c.isalnum())
            
        return clean_name(name1) == clean_name(name2)

    def generate(self):
        """Generate the consolidated JSON file"""
        try:
            # Find all block diagrams
            diagrams = self.find_block_diagrams()
            
            # Process each found diagram
            for diagram in diagrams:
                category = diagram['category']
                subcategory = diagram['subcategory']
                application = diagram['application']
                
                # Get block diagram data
                block_data = self.get_block_diagram_data(
                    diagram['diagram_path'],
                    diagram['content_path']
                )
                
                if block_data:
                    # Get application link
                    app_link = self.find_application_link(
                        category, subcategory, application
                    )
                    
                    # Build nested structure
                    if category not in self.consolidated_data:
                        self.consolidated_data[category] = {}
                    
                    if subcategory not in self.consolidated_data[category]:
                        self.consolidated_data[category][subcategory] = {}
                    
                    # Add application data
                    self.consolidated_data[category][subcategory][application] = {
                        'title': application,
                        'link': app_link,
                        'block_diagram': block_data
                    }
            
            # Save the consolidated data
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(self.consolidated_data, f, indent=2, ensure_ascii=False)
            
            logging.info(f"Successfully generated {self.output_file}")
            return True
            
        except Exception as e:
            logging.error(f"Error generating consolidated JSON: {str(e)}")
            return False

def main():
    """Main execution function"""
    try:
        generator = JSONGenerator()
        
        # Find and log all block diagrams first
        logging.info("Scanning for block diagrams...")
        diagrams = generator.find_block_diagrams()
        logging.info(f"Found {len(diagrams)} block diagrams")
        
        for diagram in diagrams:
            logging.info(f"Found diagram in {diagram['category']}/{diagram['subcategory']}/{diagram['application']}")
        
        # Generate the consolidated JSON
        logging.info("\nGenerating consolidated JSON...")
        success = generator.generate()
        
        if success:
            logging.info("Successfully generated consolidated JSON")
        else:
            logging.error("Failed to generate consolidated JSON")
            
    except Exception as e:
        logging.error(f"Unexpected error in main: {str(e)}")
        raise

if __name__ == "__main__":
    main()