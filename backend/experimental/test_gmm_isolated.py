import numpy as np
import time
from sklearn.mixture import GaussianMixture

def test_gmm():
    print("Generating synthetic data for standard GMM...")
    # Generate random features: 2000 rows, 8 features
    np.random.seed(42)
    X = np.random.randn(2000, 8)
    
    n_components = 4  # Treat each component as a regime state directly
    
    print(f"Initializing GaussianMixture (n_components={n_components})...")
    model = GaussianMixture(
        n_components=n_components,
        covariance_type="full",
        n_init=1,  # Single init is faster
        random_state=42,
        max_iter=1000,
        verbose=1
    )
    
    print("Fitting model...")
    t0 = time.time()
    model.fit(X)
    t1 = time.time()
    
    print(f"Fit complete in {t1 - t0:.2f} seconds.")
    
    log_lik = model.score(X) * len(X)
    n_params = model._n_parameters()
    bic = -2 * log_lik + n_params * np.log(len(X))
    
    print(f"Params: {n_params} | BIC: {bic:.1f}")

if __name__ == "__main__":
    test_gmm()
