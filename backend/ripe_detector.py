import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
from PIL import Image
from pathlib import Path
from tqdm import tqdm
import os

class RipeDetector(nn.Module):
    def __init__(self, dropout_rate=0.5):
        super(RipeDetector, self).__init__()
        # Lighter model: reduced channels and FC size
        # First convolutional layer: 3 input channels (RGB), 8 output channels, 3x3 kernel
        self.conv1 = nn.Conv2d(3, 16, kernel_size=3, padding=1)
        # Second convolutional layer: 8 input channels, 16 output channels, 3x3 kernel
        self.conv2 = nn.Conv2d(16, 16, kernel_size=3, padding=1)
        # Max pooling layer
        self.pool = nn.MaxPool2d(2, 2)
        # Adaptive average pooling to reduce spatial dimensions before FC
        self.adaptive_pool = nn.AdaptiveAvgPool2d((7, 7))
        # Dropout layer for regularization
        self.dropout = nn.Dropout(dropout_rate)
        # Fully connected layers - much smaller
        self.fc1 = nn.Linear(16 * 7 * 7, 32)
        self.fc2 = nn.Linear(32, 1)  # Binary classification: 1 output (fresh=1, rotten=0)

    def forward(self, x):
        x = self.pool(F.relu(self.conv1(x)))
        x = self.pool(F.relu(self.conv2(x)))
        x = self.adaptive_pool(x)  # Reduce to 7x7
        x = x.view(-1, 16 * 7 * 7)  # Flatten the feature maps
        x = F.relu(self.fc1(x))
        x = self.dropout(x)  # Apply dropout for regularization
        x = self.fc2(x)
        return x

class RipeDataset(Dataset):
    """Custom dataset for ripe/fresh fruit classification"""
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
    
    # Define transforms
    train_transform = transforms.Compose([
        transforms.Resize((256, 256)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(10),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
    
    test_transform = transforms.Compose([
        transforms.Resize((256, 256)),
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
    train_dataset = RipeDataset(train_image_paths, train_labels, transform=train_transform)
    test_dataset = RipeDataset(test_image_paths, test_labels, transform=test_transform)
    
    return train_dataset, test_dataset

def train_model(model, train_dataset, test_dataset, epochs=4, batch_size=128, learning_rate=0.001):
    """
    Train the RipeDetector model on the training dataset and evaluate on test dataset.
    
    Args:
        model: The RipeDetector model to train
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
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    
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
        
        print(f'Epoch [{epoch+1}/{epochs}] Summary:')
        print(f'  Train Loss: {epoch_loss:.4f}, Train Accuracy: {epoch_acc:.2f}%')
        print(f'  Test Loss: {avg_test_loss:.4f}, Test Accuracy: {test_acc:.2f}%')
        print('-' * 60)
    
    # Create model directory if it doesn't exist
    os.makedirs("./model", exist_ok=True)
    torch.save(model.state_dict(), "./model/ripe_detector.pth")
    print('Training completed! Model saved to ./model/ripe_detector.pth')
    return model

def load_model(path):
    """
    Load the model from the path.
    """
    model = RipeDetector()
    model.load_state_dict(torch.load(path))
    return model

def inference(model, image_path, device=None):
    """
    Inference the model on a single image.
    
    Args:
        model: The trained RipeDetector model
        image_path: Path to the image file
        device: Device to run inference on (defaults to model's device)
    
    Returns:
        Probability of being fresh (1 = fresh, 0 = rotten)
    """
    if device is None:
        device = next(model.parameters()).device
    
    # Use the same preprocessing as test data
    transform = transforms.Compose([
        transforms.Resize((256, 256)),
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
    if os.path.exists("./model/ripe_detector.pth"):
        model = load_model("./model/ripe_detector.pth")
    else:
        train_dataset, test_dataset = load_data()
        model = RipeDetector()
        trained_model = train_model(model, train_dataset, test_dataset)
    
    # Inference
    image_path = "./setup/data/dataset/Test/fresh/00000000.jpg"
    probability = inference(model, image_path)
    print(f"Probability of being fresh: {probability}")