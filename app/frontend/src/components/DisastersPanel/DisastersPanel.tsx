import React, { useEffect, useState } from 'react';
import { Dialog, DefaultButton, Label, Separator, DialogFooter, DialogType, IconButton } from '@fluentui/react';
import { fetchAzureFunctionResponse } from '../../api'; // Adjust the path to your API file
import styles from '../../pages/chat/Chat.module.css';

interface Disaster {
    name: string;
    link: string;
}

const dialogContentProps = {
    type: DialogType.largeHeader,
    title: "Choose a disaster to investigate",
  };

export const DisastersPanel = ({ isOpen, onDismiss }: { isOpen: boolean, onDismiss: (selectedDisaster: string) => void }) => {
    const [disasters, setDisasters] = useState<Disaster[]>([]);

    useEffect(() => {
        const fetchDisasters = async () => {
            try {
                const data = await fetchAzureFunctionResponse();
                setDisasters(data);
            } catch (error) {
                const data = [{"name": "Arkansas Severe Storms", "link": "https://fema.gov/disaster/4788"}, {"name": "Florida Hurricane Debby", "link": "/disaster/4806"}, {"name": "Florida Severe Storms", "link": "/disaster/4794"}, {"name": "Hermit's Peak/Calf Canyon Fire", "link": "/disaster/current/hermits-peak"}, {"name": "Iowa Severe Storms (April)", "link": "/disaster/4779"}, {"name": "Iowa Severe Storms (May)", "link": "/disaster/4784"}, {"name": "Kentucky Severe Storms", "link": "/disaster/4804"}, {"name": "Mississippi Severe Storms", "link": "/disaster/4790"}, {"name": "Missouri Severe Storms", "link": "/disaster/4803"}, {"name": "New Mexico Wildfires", "link": "/disaster/4795"}, {"name": "Oklahoma Severe Storms (April)", "link": "/disaster/4776"}, {"name": "Oklahoma Severe Storms (May)", "link": "/disaster/4791"}, {"name": "Texas Hurricane Beryl", "link": "/disaster/4798"}, {"name": "Texas Severe Storms", "link": "/disaster/4781"}, {"name": "Wildfire Actions", "link": "/disaster/wildfire-actions"}]
                setDisasters(data);
                console.log('Error fetching disasters:', error);
            }
        };

        if (isOpen) {
            fetchDisasters();
        }
    }, [isOpen]);

    return (
        <Dialog
            isOpen={isOpen}
            isBlocking={true}
            closeButtonAriaLabel="Close"
            dialogContentProps={dialogContentProps}
        >
            {disasters.length === 0 ? (
                <Label>No disasters available</Label>
            ) : (
                <table className={styles.disastersTable}>
                    {/* <thead>
                        <tr>
                            <th>Name</th>
                            <th>Info</th>
                        </tr>
                    </thead> */}
                    <tbody>
                        {disasters.map((disaster, index) => (
                            <tr key={index}>
                                <td>{disaster.name}</td>
                                <td>
                                    <IconButton
                                        style={{ color: "black" }}
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
            )}
        </Dialog>
    );
};

