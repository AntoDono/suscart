import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
from torchvision.models import resnet18, ResNet18_Weights
from PIL import Image
from pathlib import Path
from tqdm import tqdm
import os

class FreshDetector(nn.Module):
    def __init__(self, dropout_rate=0.5, pretrained=True):
        super(FreshDetector, self).__init__()
        # Use pretrained ResNet18 as backbone
        if pretrained:
            self.backbone = resnet18(weights=ResNet18_Weights.IMAGENET1K_V1)
        else:
            self.backbone = resnet18(weights=None)
        
        # Replace the final fully connected layer
        # ResNet18's fc layer expects 512 features
        num_features = self.backbone.fc.in_features
        
        # Remove the original classifier
        self.backbone.fc = nn.Identity()
        
        # Add custom classifier with dropout for regularization
        self.classifier = nn.Sequential(
            nn.Dropout(dropout_rate),
            nn.Linear(num_features, 256),
            nn.ReLU(),
            nn.Dropout(dropout_rate),
            nn.Linear(256, 1)  # Binary classification: 1 output (fresh=1, rotten=0)
        )

    def forward(self, x):
        # Extract features using ResNet backbone
        features = self.backbone(x)
        # Apply classifier
        output = self.classifier(features)
        return output

class FreshDataset(Dataset):
    """Custom dataset for fresh/rotten fruit classification"""
    def __init__(self, image_paths, labels, transform=None):
        self.image_paths = image_paths
        self.labels = labels
        self.transform = transform
    
    def __len__(self):
        return len(self.image_paths)
    
    def __getitem__(self, idx):
        image_path = self.image_paths[idx]
        label = self.labels[idx]
        
        # Load image
        try:
            image = Image.open(image_path).convert('RGB')
        except Exception as e:
            print(f"Error loading image {image_path}: {e}")
            # Return a black image if loading fails
            image = Image.new('RGB', (224, 224), color='black')
        
        # Apply transforms
        if self.transform:
            image = self.transform(image)
        
        return image, label

def load_data(path="./setup/data/dataset"):
    """
    Load data from dataset directory.
    Separates fresh (label=1) and rotten (label=0) images.
    
    Args:
        path: Path to the dataset directory containing Train and Test folders
    
    Returns:
        train_dataset: Dataset for training
        test_dataset: Dataset for testing
    """
    path = Path(path)
    train_path = path / "Train"
    test_path = path / "Test"
    
    # Define transforms - using 224x224 for ImageNet pretrained models
    # More aggressive augmentation for better generalization
    train_transform = transforms.Compose([
        transforms.Resize((256, 256)),
        transforms.RandomCrop(224),  # Random crop for better generalization
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomRotation(15),
        transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2, hue=0.1),
        transforms.RandomAffine(degrees=0, translate=(0.1, 0.1)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
    
    test_transform = transforms.Compose([
        transforms.Resize((224, 224)),  # Standard ImageNet size
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
    
    def collect_images(folder_path):
        """Collect all images from fresh and rotten folders"""
        image_paths = []
        labels = []
        
        if not folder_path.exists():
            raise ValueError(f"Directory {folder_path} does not exist")
        
        # Get all subdirectories
        for subdir in folder_path.iterdir():
            if not subdir.is_dir():
                continue
            
            folder_name = subdir.name.lower()
            
            # Determine label: fresh = 1, rotten = 0
            if folder_name.startswith('fresh'):
                label = 1  # fresh
            elif folder_name.startswith('rotten'):
                label = 0  # rotten
            else:
                continue  # Skip folders that don't match pattern
            
            # Collect all image files
            image_extensions = {'.png', '.jpg', '.jpeg'}
            for img_file in subdir.rglob('*'):
                if img_file.suffix.lower() in image_extensions:
                    image_paths.append(img_file)
                    labels.append(label)
        
        return image_paths, labels
    
    # Load training data
    train_image_paths, train_labels = collect_images(train_path)
    print(f"Loaded {len(train_image_paths)} training images")
    print(f"  Fresh: {sum(train_labels)} images")
    print(f"  Rotten: {len(train_labels) - sum(train_labels)} images")
    
    # Load test data
    test_image_paths, test_labels = collect_images(test_path)
    print(f"Loaded {len(test_image_paths)} test images")
    print(f"  Fresh: {sum(test_labels)} images")
    print(f"  Rotten: {len(test_labels) - sum(test_labels)} images")
    
    # Create datasets
    train_dataset = FreshDataset(train_image_paths, train_labels, transform=train_transform)
    test_dataset = FreshDataset(test_image_paths, test_labels, transform=test_transform)
    
    return train_dataset, test_dataset

def train_model(model, train_dataset, test_dataset, epochs=15, batch_size=32, learning_rate=0.0001):
    """
    Train the FreshDetector model on the training dataset and evaluate on test dataset.
    
    Args:
        model: The FreshDetector model to train
        train_dataset: Training dataset
        test_dataset: Test dataset
        epochs: Number of training epochs
        batch_size: Batch size for training
        learning_rate: Learning rate for optimizer
    
    Returns:
        Trained model
    """
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")
    
    model = model.to(device)
    
    # Create data loaders
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=2)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False, num_workers=2)
    
    # Loss function and optimizer
    criterion = nn.BCEWithLogitsLoss()  # Binary cross-entropy for binary classification
    
    # Use different learning rates for pretrained backbone vs new classifier
    # Freeze backbone initially, then fine-tune with lower learning rate
    backbone_params = list(model.backbone.parameters())
    classifier_params = list(model.classifier.parameters())
    
    # Start with frozen backbone for a few epochs, then fine-tune
    optimizer = torch.optim.Adam([
        {'params': classifier_params, 'lr': learning_rate * 10},  # Higher LR for new layers
        {'params': backbone_params, 'lr': learning_rate}  # Lower LR for pretrained layers
    ])
    
    # Learning rate scheduler for better convergence
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=5, gamma=0.5)
    
    # Training loop
    for epoch in range(epochs):
        print(f"Epoch {epoch+1}/{epochs}")
        model.train()
        running_loss = 0.0
        correct_train = 0
        total_train = 0
        
        pbar = tqdm(train_loader, desc=f"Training")
        for batch_idx, (images, labels) in enumerate(pbar):
            images = images.to(device)
            labels = labels.float().unsqueeze(1).to(device)  # Convert to float and add dimension for BCE
            
            # Forward pass
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            
            # Backward pass
            loss.backward()
            optimizer.step()
            
            # Statistics
            running_loss += loss.item()
            predictions = torch.sigmoid(outputs) > 0.5
            correct_train += (predictions.float() == labels).sum().item()
            total_train += labels.size(0)
            
            # Print progress every 100 batches
            if (batch_idx + 1) % 100 == 0:
                pbar.set_postfix(loss=loss.item(), accuracy=100 * correct_train / total_train)
        
        # Calculate average loss and accuracy for the epoch
        epoch_loss = running_loss / len(train_loader)
        epoch_acc = 100 * correct_train / total_train
        
        # Evaluate on test set
        model.eval()
        correct_test = 0
        total_test = 0
        test_loss = 0.0
        
        with torch.no_grad():
            for images, labels in test_loader:
                images = images.to(device)
                labels = labels.float().unsqueeze(1).to(device)
                
                outputs = model(images)
                loss = criterion(outputs, labels)
                test_loss += loss.item()
                
                predictions = torch.sigmoid(outputs) > 0.5
                correct_test += (predictions.float() == labels).sum().item()
                total_test += labels.size(0)
        
        test_acc = 100 * correct_test / total_test
        avg_test_loss = test_loss / len(test_loader)
        
        # Update learning rate
        scheduler.step()
        
        # Get learning rates for both parameter groups
        lrs = scheduler.get_last_lr()
        
        print(f'Epoch [{epoch+1}/{epochs}] Summary:')
        print(f'  Train Loss: {epoch_loss:.4f}, Train Accuracy: {epoch_acc:.2f}%')
        print(f'  Test Loss: {avg_test_loss:.4f}, Test Accuracy: {test_acc:.2f}%')
        print(f'  Learning Rate (classifier): {lrs[0]:.6f}, (backbone): {lrs[1]:.6f}')
        print('-' * 60)
    
    # Create model directory if it doesn't exist
    os.makedirs("./model", exist_ok=True)
    torch.save(model.state_dict(), "./model/fresh_detector.pth")
    print('Training completed! Model saved to ./model/fresh_detector.pth')
    return model

def load_model(path, device=None, pretrained=True):
    """
    Load the model from the path.
    Handles loading models saved on CUDA when running on CPU.
    
    Args:
        path: Path to the model file
        device: Target device (None for auto-detect, 'cpu', 'cuda', or torch.device)
        pretrained: Whether to use pretrained ResNet weights (default: True)
    
    Returns:
        FreshDetector: Loaded model
    """
    model = FreshDetector(pretrained=pretrained)
    
    # Determine device for loading
    if device is None:
        if torch.cuda.is_available():
            device = torch.device('cuda')
        else:
            device = torch.device('cpu')
    elif isinstance(device, str):
        device = torch.device(device)
    
    # Map the loaded model to the target device
    # This handles cases where model was saved on CUDA but loading on CPU
    model.load_state_dict(torch.load(path, map_location=device))
    model = model.to(device)
    return model

def inference(model, image_path, device=None):
    """
    Inference the model on a single image.
    
    Args:
        model: The trained FreshDetector model
        image_path: Path to the image file
        device: Device to run inference on (defaults to model's device)
    
    Returns:
        Probability of being fresh (1 = fresh, 0 = rotten)
    """
    if device is None:
        device = next(model.parameters()).device
    
    # Use the same preprocessing as test data (224x224 for ResNet)
    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
    
    image = Image.open(image_path).convert('RGB')
    image = transform(image)
    image = image.unsqueeze(0).to(device)
    
    model.eval()
    with torch.no_grad():
        output = model(image)
        probability = torch.sigmoid(output).item()  # Convert logit to probability
    
    return probability  # Returns value between 0 (rotten) and 1 (fresh)

if __name__ == "__main__":
    if os.path.exists("./model/fresh_detector.pth"):
        print("Loading existing model...")
        model = load_model("./model/fresh_detector.pth")
        print("Model loaded successfully!")
    else:
        print("No existing model found. Training new ResNet-based model...")
        train_dataset, test_dataset = load_data()
        model = FreshDetector(pretrained=True)  # Use pretrained ResNet18
        print("Starting training with ResNet18 backbone...")
        trained_model = train_model(model, train_dataset, test_dataset, epochs=15)
        model = trained_model
    
    # Inference
    img1 = "./setup/data/dataset/Test/freshapples/a_f001.png"
    img2 = "./setup/data/dataset/Test/rottenapples/a_r001.png"
    if os.path.exists(img1) and os.path.exists(img2):
        probability1 = inference(model, img1)
        probability2 = inference(model, img2)
        print(f"\nTest Results:")
        print(f"Fresh apple probability: {probability1:.4f} ({'FRESH' if probability1 > 0.5 else 'ROTTEN'})")
        print(f"Rotten apple probability: {probability2:.4f} ({'FRESH' if probability2 > 0.5 else 'ROTTEN'})")
    else:
        print("Test images not found. Skipping inference test.")

