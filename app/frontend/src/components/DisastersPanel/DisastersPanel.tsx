import React, { useEffect, useState } from 'react';
import { Dialog, Label, Spinner, SpinnerSize, DialogType, IconButton } from '@fluentui/react';
import { fetchAzureFunctionResponse } from '../../api'; // Adjust the path to your API file
import styles from '../../pages/chat/Chat.module.css';

interface Disaster {
    name: string;
    link: string;
    state: string;
    area: string;
    declarationDate: string;
}

const dialogContentProps = {
    type: DialogType.largeHeader,
    title: "Choose a disaster to investigate",
};

const dialogStyles = {
    main: {
        maxWidth: '600px !important',
        minWidth: '600px !important',
    }
};

// Mapping of state codes to full state names
const stateCodeToName: { [key: string]: string } = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas', 'CA': 'California',
    'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware', 'FL': 'Florida', 'GA': 'Georgia',
    'HI': 'Hawaii', 'ID': 'Idaho', 'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa',
    'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
    'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi', 'MO': 'Missouri',
    'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada', 'NH': 'New Hampshire', 'NJ': 'New Jersey',
    'NM': 'New Mexico', 'NY': 'New York', 'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio',
    'OK': 'Oklahoma', 'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
    'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah', 'VT': 'Vermont',
    'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia', 'WI': 'Wisconsin', 'WY': 'Wyoming'
};

export const DisastersPanel = ({ isOpen, onDismiss }: { isOpen: boolean, onDismiss: (selectedDisaster: string) => void }) => {
    const [disasters, setDisasters] = useState<Disaster[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        // Function to fetch disaster data from the FEMA API
        const fetchDisasters = async () => {
            // Set loading state to true and clear any previous errors
            setIsLoading(true);
            setError(null);
    
            try {
                // URL for the FEMA Disaster Declarations Summaries API
                const url = "https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries";
    
                // Calculate the date 30 days ago to filter recent disasters
                const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString();
    
                // Create URL parameters for the API request
                const params = new URLSearchParams({
                    "$orderby": "declarationDate desc", // Order by declaration date in descending order
                    "$filter": `declarationDate ge ${thirtyDaysAgo}`, // Filter disasters declared in the last 30 days
                    "$top": "30" // Limit the number of results to 30
                });
    
                // Fetch the disaster data from the FEMA API
                const response = await fetch(`${url}?${params}`);
    
                // Check if the response was successful
                if (!response.ok) {
                    throw new Error('Failed to fetch disaster data from FEMA API');
                }
    
                // Parse the response data as JSON
                const data = await response.json();
    
                // Format the disaster data for display
                const formattedData = data.DisasterDeclarationsSummaries.map((disaster: any) => ({
                    name: disaster.declarationTitle, // Title of the disaster declaration
                    link: `https://www.fema.gov/disaster/${disaster.disasterNumber}`, // Link to the disaster details
                    state: stateCodeToName[disaster.state] || disaster.state, // State name or code if not found
                    area: disaster.designatedArea, // Designated area of the disaster
                    declarationDate: new Date(disaster.declarationDate).toLocaleDateString() // Declaration date in local format
                }));
    
                // Update the state with the formatted disaster data
                setDisasters(formattedData);
            } catch (error) {
                // Log and display any errors that occur during the fetch process
                console.error('Error fetching disasters:', error);
                setError('Failed to fetch disaster data. Please try again later.');
            } finally {
                // Set loading state to false after the fetch is complete
                setIsLoading(false);
            }
        };
    
        // Only fetch disasters when the component is open
        if (isOpen) {
            fetchDisasters();
        }
    
        if (isOpen) {
            fetchDisasters();
        }
    }, [isOpen]);

    return (
        <Dialog
            hidden={!isOpen}
            onDismiss={() => onDismiss('')}
            dialogContentProps={dialogContentProps}
            modalProps={{
                isBlocking: false,
                styles: dialogStyles
            }}
        >
            {isLoading ? (
                <Spinner size={SpinnerSize.large} label="Loading disasters..." />
            ) : error ? (
                <Label>{error}</Label>
            ) : disasters.length === 0 ? (
                <Label>No disasters available</Label>
            ) : (
                <div className={styles.disastersTableContainer}>
                    <table className={styles.disastersTable}>
                        <thead>
                            <tr>
                                <th>Name</th>
                                <th>State</th>
                                <th>Area</th>
                                <th>Declaration Date</th>
                                <th>Info</th>
                                <th>Select</th>
                            </tr>
                        </thead>
                        <tbody>
                            {disasters.map((disaster, index) => (
                                <tr key={index}>
                                    <td>{disaster.name}</td>
                                    <td>{disaster.state}</td>
                                    <td>{disaster.area}</td>
                                    <td>{disaster.declarationDate}</td>
                                    <td>
                                        <IconButton
                                            iconProps={{ iconName: "Info" }}
                                            title="FEMA Details"
                                            ariaLabel="FEMA Details"
                                            onClick={() => window.open(disaster.link)}
                                        />
                                    </td>
                                    <td>
                                        <IconButton
                                            style={{ color: "green" }}
                                            iconProps={{ iconName: "Accept" }}
                                            title="Pick this disaster"
                                            ariaLabel="Pick this disaster"
                                            onClick={() => onDismiss(disaster.name)}
                                        />
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </Dialog>
    );
};